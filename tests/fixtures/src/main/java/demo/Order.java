package demo;
import org.axonframework.commandhandling.CommandHandler;
import org.axonframework.eventsourcing.EventSourcingHandler;
import org.axonframework.eventhandling.EventHandler;
import static org.axonframework.modelling.command.AggregateLifecycle.apply;
class Order {
    @CommandHandler Order(CreateOrder command) { apply(new OrderCreated(command.id())); }
    @CommandHandler void cancel(CancelOrder command) { apply(new OrderCancelled()); }
    @CommandHandler void unknown(UnknownCommand command) { apply(makeEvent()); }
    @EventSourcingHandler void on(OrderCreated event) { }
}
class OrderProjection {
    @EventHandler void on(OrderCreated event) { }
    @EventHandler void on(OrderCancelled event) { }
}
record CreateOrder(String id) { }
record CancelOrder() { }
record UnknownCommand() { }
record OrderCreated(String id) { }
record OrderCancelled() { }
