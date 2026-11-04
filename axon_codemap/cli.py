import argparse
import json
import sys
from pathlib import Path
from tree_sitter import Language, Parser
import tree_sitter_java

PARSER = Parser(Language(tree_sitter_java.language()))
EXCLUDE = {'.git', 'target', 'build', 'out', '.gradle', 'node_modules', 'vendor'}
TYPES = {'class_declaration', 'interface_declaration', 'record_declaration', 'enum_declaration'}
METHODS = {'method_declaration', 'constructor_declaration'}

def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)

def text(node, data):
    return data[node.start_byte:node.end_byte].decode('utf-8') if node else ''

def annotations(node, data):
    modifiers = next((c for c in node.named_children if c.type == 'modifiers'), None)
    return {text(c.child_by_field_name('name'), data).split('.')[-1] for c in (modifiers.named_children if modifiers else []) if c.type in ('annotation', 'marker_annotation')}

def location(path, node):
    return {'file': path, 'line': node.start_point.row + 1}

def scan(root, include_tests=False):
    files = []
    warnings = []
    for path in sorted(root.rglob('*.java')):
        rel = path.relative_to(root)
        if any(part in EXCLUDE for part in rel.parts) or (not include_tests and ('test' in rel.parts or 'tests' in rel.parts)):
            continue
        try:
            data = path.read_bytes()
            tree = PARSER.parse(data)
        except (OSError, ValueError) as exc:
            warnings.append(f'{rel}: {exc}')
            continue
        if tree.root_node.has_error:
            warnings.append(f'{rel}: Java syntax errors; results may be incomplete')
        package, imports, wildcards, all_imports = '', {}, [], []
        for n in tree.root_node.named_children:
            s = text(n, data)
            if n.type == 'package_declaration': package = s[len('package '):].rstrip(';').strip()
            if n.type == 'import_declaration':
                imp = s[len('import '):].rstrip(';').strip()
                is_static = imp.startswith('static ')
                if is_static: imp = imp[len('static '):].strip()
                all_imports.append(imp)
                if not is_static:
                    if imp.endswith('.*'): wildcards.append(imp[:-2])
                    else: imports[imp.split('.')[-1]] = imp
        files.append({'path': rel.as_posix(), 'data': data, 'tree': tree, 'package': package, 'imports': imports, 'wildcards': wildcards, 'all_imports': all_imports})
    declared = set()
    for f in files:
        for n in walk(f['tree'].root_node):
            if n.type in TYPES:
                name = text(n.child_by_field_name('name'), f['data'])
                declared.add('.'.join(filter(None, (f['package'], name))))
    def resolve(name, f):
        name = name.strip()
        if '.' in name: return name
        if name in f['imports']: return f['imports'][name]
        local = '.'.join(filter(None, (f['package'], name)))
        if local in declared: return local
        candidates = [p + '.' + name for p in f['wildcards'] if p + '.' + name in declared]
        if len(candidates) == 1: return candidates[0]
        # Preserve uncertainty, rather than joining unrelated simple names.
        if len(candidates) > 1:
            warnings.append(f"{f['path']}: ambiguous type {name}: {', '.join(candidates)}")
            return f"?{f['path']}:{name}"
        return local
    # Aggregate by declared Java package across modules. Dependencies are import evidence,
    # not an attempted whole-program symbol-resolution or call graph.
    packages = {}
    for f in files:
        package = f['package']
        if package not in packages:
            packages[package] = {'name': package, 'files': [], 'uses': set()}
        methods = []
        def inventory(n, owner=''):
            if n.type in TYPES:
                name = text(n.child_by_field_name('name'), f['data'])
                owner = f'{owner}.{name}' if owner else name
            if n.type in METHODS and owner:
                name = text(n.child_by_field_name('name'), f['data'])
                params = text(n.child_by_field_name('parameters'), f['data'])
                methods.append({'name': f'{owner}.{name}{params}', 'line': n.start_point.row + 1})
            for child in n.named_children: inventory(child, owner)
        inventory(f['tree'].root_node)
        packages[package]['files'].append({'path': f['path'], 'methods': methods})
    for f in files:
        for imp in f['all_imports']:
            target = imp[:-2] if imp.endswith('.*') else imp
            # Wildcard package imports name the package itself. Other imports,
            # including static members and nested types, begin with a declared type.
            dest = target if target in packages and imp.endswith('.*') else None
            if dest is None:
                parts = target.split('.')
                while parts:
                    candidate = '.'.join(parts)
                    if candidate in declared:
                        dest = candidate.rpartition('.')[0]
                        break
                    parts.pop()
            if dest is not None and dest != f['package'] and dest in packages:
                packages[f['package']]['uses'].add(dest)
    for package in packages.values(): package['uses'] = sorted(package['uses'])

    commands, consumers = [], []
    for f in files:
        data = f['data']
        def visit(n, owner=None):
            if n.type in TYPES:
                owner = {'name': text(n.child_by_field_name('name'), data), 'annotations': annotations(n, data)}
            if n.type in METHODS and owner:
                anns = annotations(n, data)
                if anns & {'CommandHandler', 'EventHandler', 'EventSourcingHandler'}:
                    params = n.child_by_field_name('parameters')
                    ps = [p for p in (params.named_children if params else []) if p.type in ('formal_parameter', 'spread_parameter')]
                    # Axon payload is ordinarily the first argument; metadata-only signatures need explicit configuration.
                    typ = text(ps[0].child_by_field_name('type'), data) if ps else ''
                    if typ:
                        handler = {'type': resolve(typ, f), 'owner': owner['name'], 'method': text(n.child_by_field_name('name'), data), **location(f['path'], n)}
                        if 'CommandHandler' in anns:
                            handler['events'] = []
                            body = n.child_by_field_name('body')
                            if body:
                                for call in walk(body):
                                    if call.type != 'method_invocation' or text(call.child_by_field_name('name'), data) != 'apply': continue
                                    obj = text(call.child_by_field_name('object'), data)
                                    if obj not in ('', 'AggregateLifecycle', 'org.axonframework.modelling.command.AggregateLifecycle'): continue
                                    args = call.child_by_field_name('arguments')
                                    first = args.named_children[0] if args and args.named_children else None
                                    if first and first.type == 'object_creation_expression':
                                        event = text(first.child_by_field_name('type'), data)
                                        if event: handler['events'].append({'type': resolve(event, f), **location(f['path'], call)})
                                    else:
                                        warnings.append(f"{f['path']}:{call.start_point.row + 1}: apply payload is not a direct constructor; event not resolved")
                            commands.append(handler)
                        if 'EventHandler' in anns and 'EventSourcingHandler' not in anns:
                            handler['kind'] = 'event handler'
                            consumers.append(handler)
            for child in n.named_children: visit(child, owner)
        visit(f['tree'].root_node)
    return {'commands': commands, 'consumers': consumers, 'warnings': sorted(set(warnings)), 'fileCount': len(files), 'packages': sorted(packages.values(), key=lambda p: p['name'])}

def main():
    ap = argparse.ArgumentParser(description='Create a standalone Java package and Axon flow map from source.')
    ap.add_argument('-root', '--root', type=Path, default=Path('.'), help='Java project root (default: current directory)')
    ap.add_argument('-o', '--output', type=Path, default=Path('code-map.html'))
    ap.add_argument('--include-tests', action='store_true')
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir(): ap.error(f'not a directory: {root}')
    model = scan(root, args.include_tests)
    model['root'] = root.name
    raw = json.dumps(model, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = Path(__file__).with_name('page.html').read_text(encoding='utf-8')
    args.output.write_text(template.replace('/*__DATA__*/', raw), encoding='utf-8')
    print(f"Wrote {args.output}: {model['fileCount']} Java files, {len(model['commands'])} command handlers, {len(model['consumers'])} event handlers, {len(model['warnings'])} warnings")
    if not model['fileCount']: print('Warning: no Java files found', file=sys.stderr)
if __name__ == '__main__': main()
