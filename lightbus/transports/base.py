from typing import Sequence, Tuple, Any, Hashable
from uuid import uuid1

from lightbus.api import Api
from lightbus.message import RpcMessage, EventMessage, ResultMessage
from lightbus.utilities import MessageConsumptionContext


class RpcTransport(object):
    """Implement the sending and receiving of RPC calls"""

    async def call_rpc(self, rpc_message: RpcMessage, options: dict):
        """Publish a call to a remote procedure"""
        raise NotImplementedError()

    async def consume_rpcs(self, apis: Sequence[Api]) -> Sequence[RpcMessage]:
        """Consume RPC calls for the given API"""
        raise NotImplementedError()


class ResultTransport(object):
    """Implement the send & receiving of results

    """

    def get_return_path(self, rpc_message: RpcMessage) -> str:
        raise NotImplementedError()

    async def send_result(self, rpc_message: RpcMessage, result_message: ResultMessage, return_path: str):
        """Send a result back to the caller

        Args:
            rpc_message (): The original message received from the client
            result_message (): The result message to be sent back to the client
            return_path (str): The string indicating where to send the result.
                As generated by :ref:`get_return_path()`.
        """
        raise NotImplementedError()

    async def receive_result(self, rpc_message: RpcMessage, return_path: str, options: dict) -> ResultMessage:
        """Receive the result for the given message

        Args:
            rpc_message (): The original message sent to the server
            return_path (str): The string indicated where to receive the result.
                As generated by :ref:`get_return_path()`.
            options (dict): Dictionary of options specific to this particular backend
        """
        raise NotImplementedError()


class EventTransport(object):
    """ Implement the sending/consumption of events over a given transport.

    The simplest implementation should simply be capable of:

        1. Consuming all events
        2. Sending events

    However, consuming all events will probably be unnecessary in most situations.
    You can therefore selectively listen for events by implementing
    ``start_listening_for()`` and ``stop_listening_for()``.

    Implementing these methods will have several benefits:

      * Will reduce resource use
      * Will allow for dynamically changing listened-for events at runtime

    See Also:

        lightbus.RedisEventTransport: Implements the start_listening_for()
            and stop_listening_for() methods

    """

    async def send_event(self, event_message: EventMessage, options: dict):
        """Publish an event"""
        raise NotImplementedError()

    def consume_events(self):
        return MessageConsumptionContext(
            fetch=self.fetch_events,
            on_consumed=self.consumption_complete,
        )

    async def fetch_events(self) -> Tuple[Sequence[EventMessage], Any]:
        """Consume RPC events for the given API

        Must return a tuple, where the first item is a iterable of
        event messages and the second item is an arbitrary value which will
        be passed to consumption_complete() (below) should the events
        be executed successfully.

        Events that the bus is not listening for may be returned, they
        will simply be ignored.

        """
        raise NotImplementedError()

    async def consumption_complete(self, extra):
        pass

    async def start_listening_for(self, api_name: str, event_name: str, options: dict):
        """Instruct this transport to start listening for the given event"""
        pass

    async def stop_listening_for(self, api_name: str, event_name: str):
        """Instruct this transport to stop listening for the given event"""
        pass

    def get_listener_group_key(self, api_name: str, event_name: str, options: dict) -> Hashable:
        """Get a key to uniquely identify a group of listeners for the given parameters

        This method allows the backend to control how the bus connects incoming
        events to listeners.

        There are two scenarios possible when the bus' listen() method is called:

            1. Call the EventTransport's start_listening_for() method and subsequently expect
               the event transport to provide the relevant events (via fetch_events()).
               Upon receiving these events the bus will call the callback provided to listen().

            2. Realise the specified event is already being consumed by the EventTransport in question.
               Therefore no call to start_listening_for() is needed, and the provided callable
               can just be add to the list of things to call upon receiving the specified events.

        Scenario 2 in effect creates a grouping of listeners. The EventTransport is consuming a single
        stream of events and passing each event to the bus, but the bus is calling multiple listeners callbacks for
        each event. This reduces the number of network connections, reduces network traffic, and reduces the
        number of messages which need to be decoded.

        However, in some cases grouping listeners together does not make sense. For example, consider a
        system where past events are available. One listener may just want to listen for any
        auth.user_signup events in real-time. On the other hand, another listener may want
        to do the same but to start by streaming all events ever.

        In the former case the callback only wants events as they happen (maybe it is responsible
        for sending the signup emails to new users), whereas the second case expects all signup events ever
        followed by a real-time stream (maybe it is populating a database or report).

        The RedisEventTransport supports this, and be be specified via ``options['since']``.

        We therefore need a way to distinguish between these two cases. Otherwise it would be easy
        to accidentally re-send all your signup emails to every user ever, for example.

        You should implement this method to return different values for listeners which cannot
        be grouped together, and to return the same values for listeners which can be grouped together.

        The default implementation simply returns a random UUID in all cases, therefore
        no grouping will occur. This is the safest option, but also will not provide any
        of the performance benefits detailed above.

        """
        return uuid1()
