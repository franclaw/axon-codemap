# Axon Code Map

Generate a single self-contained, searchable HTML map of Java Axon command handlers → events → event handlers. Inspired by [codemap](https://github.com/peterretief/codemap); this is an independent implementation, not a fork. Source stays on your machine and the resulting HTML needs no server, Java build, Java runtime, or external assets.

## Example: AxonIQ bike rental workshop

This map was generated from [AxonIQ/bike-rental-workshop-2026](https://github.com/AxonIQ/bike-rental-workshop-2026) at commit [`8d9fdd0`](https://github.com/AxonIQ/bike-rental-workshop-2026/tree/8d9fdd09b793cec619c0a40f9f9fc7ae138741fd). The scan found 35 Java files, 8 command handlers and 8 event handlers. For example, `RegisterBikeCommand` applies `BikeRegisteredEvent`, consumed by `BikeStatusProjection`.

![Axon Code Map showing the bike rental workshop command, event, and projection](docs/bike-rental-workshop.png)

[Download the generated workshop map](examples/bike-rental-workshop.html) and open it locally (GitHub displays HTML source rather than running the page). To reproduce:

```sh
git clone https://github.com/AxonIQ/bike-rental-workshop-2026.git
git -C bike-rental-workshop-2026 checkout 8d9fdd09b793cec619c0a40f9f9fc7ae138741fd
axon-codemap --root bike-rental-workshop-2026 -o bike-rental-workshop.html
```

## Install and use

Requires Python 3.10+ and pip. From this repository:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install .
axon-codemap --root /path/to/java-project -o code-map.html
```

Open `code-map.html` in a browser. `--include-tests` includes test directories; otherwise `test` and `tests` directories are omitted, along with common build and vendor directories. Multi-module trees are scanned recursively. Search matches fully-qualified types, handler names and source paths. Expand a command to inspect its detected events and consumers. All consumers are also listed separately, including those without a detected producer.

To try the included example:

```sh
axon-codemap --root tests/fixtures -o example.html
```

## What it detects

- Methods or constructors annotated `@CommandHandler`, using the first parameter as the command payload.
- Direct `apply(new Event(...))` and `AggregateLifecycle.apply(new Event(...))` inside a command handler, including conditional branches. Each apply is shown with its source line.
- Methods annotated `@EventHandler` as consumers. `@EventSourcingHandler` is deliberately excluded: it usually rebuilds aggregate state, not a projection. A regular event handler is a **possible** projection; Axon also uses these for other purposes.
- Simple type names are resolved using explicit imports, declarations in the same package, and unambiguous wildcard imports among scanned sources. Fully-qualified names are retained. Matching requires the same resolved name, not just a matching short name.

## Important limits

This is a static source map, not a runtime execution trace: a shown event might only be emitted conditionally, and consumer execution is not guaranteed. It does **not** follow helper methods, variables passed to `apply`, factory methods, returned events, inheritance, event gateways, sagas, custom/composed annotations, or runtime configuration. Unrecognized apply payloads and syntax errors are reported in the page. Unscanned external types, nested types, wildcard imports, annotation payload overrides, and unusual parameter ordering may not resolve correctly. Check source paths and line numbers when interpreting the map. Do not treat missing links as proof that a relationship cannot happen.

## Tests

```sh
python -m unittest discover -s tests -v
```
