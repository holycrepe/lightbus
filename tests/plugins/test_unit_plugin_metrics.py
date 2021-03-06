import asyncio
import pytest

from lightbus.api import registry, Api, Event
from lightbus.bus import BusNode
from lightbus.message import RpcMessage, EventMessage
from lightbus.plugins import manually_set_plugins
from lightbus.plugins.metrics import MetricsPlugin


pytestmark = pytest.mark.unit


class TestApi(Api):
    my_event = Event(arguments=['f'])

    def my_method(self, f=None):
        return 'value'

    class Meta:
        name = 'example.test'


@pytest.mark.run_loop
async def test_remote_rpc_call(dummy_bus: BusNode, get_dummy_events):
    # Setup the bus and do the call
    manually_set_plugins(plugins={'metrics': MetricsPlugin()})
    registry.add(TestApi())
    await dummy_bus.example.test.my_method.call_async(f=123)

    # What events were fired?
    event_messages = get_dummy_events()
    assert len(event_messages) == 2

    # rpc_call_sent
    assert event_messages[0].api_name == 'internal.metrics'
    assert event_messages[0].event_name == 'rpc_call_sent'
    # Pop these next two as the values are variable
    assert event_messages[0].kwargs.pop('timestamp')
    assert event_messages[0].kwargs.pop('rpc_id')
    assert event_messages[0].kwargs.pop('process_name')
    assert event_messages[0].kwargs == {
        'api_name': 'example.test',
        'procedure_name': 'my_method',
        'kwargs': {'f': 123},
    }

    # rpc_response_received
    assert event_messages[1].api_name == 'internal.metrics'
    assert event_messages[1].event_name == 'rpc_response_received'
    # Pop these next two as the values are variable
    assert event_messages[1].kwargs.pop('timestamp')
    assert event_messages[1].kwargs.pop('rpc_id')
    assert event_messages[1].kwargs.pop('process_name')
    assert event_messages[1].kwargs == {
        'api_name': 'example.test',
        'procedure_name': 'my_method',
    }


@pytest.mark.run_loop
async def test_local_rpc_call(dummy_bus: BusNode, rpc_consumer, get_dummy_events, mocker):
    mocker.patch.object(dummy_bus.bus_client.rpc_transport, '_get_fake_messages', return_value=[
        RpcMessage(rpc_id='123abc', api_name='example.test', procedure_name='my_method', kwargs={'f': 123})
    ])

    # Setup the bus and do the call
    manually_set_plugins(plugins={'metrics': MetricsPlugin()})
    registry.add(TestApi())

    # The dummy transport will fire an every every 0.1 seconds
    await asyncio.sleep(0.15)

    event_messages = get_dummy_events()
    assert len(event_messages) == 2, event_messages

    # before_rpc_execution
    assert event_messages[0].api_name == 'internal.metrics'
    assert event_messages[0].event_name == 'rpc_call_received'
    assert event_messages[0].kwargs.pop('timestamp')
    assert event_messages[0].kwargs.pop('process_name')
    assert event_messages[0].kwargs == {
        'api_name': 'example.test',
        'procedure_name': 'my_method',
        'rpc_id': '123abc',
    }

    # after_rpc_execution
    assert event_messages[1].api_name == 'internal.metrics'
    assert event_messages[1].event_name == 'rpc_response_sent'
    assert event_messages[1].kwargs.pop('timestamp')
    assert event_messages[1].kwargs.pop('process_name')
    assert event_messages[1].kwargs == {
        'api_name': 'example.test',
        'procedure_name': 'my_method',
        'rpc_id': '123abc',
        'result': 'value',
    }


@pytest.mark.run_loop
async def test_send_event(dummy_bus: BusNode, get_dummy_events):
    manually_set_plugins(plugins={'metrics': MetricsPlugin()})
    registry.add(TestApi())
    await dummy_bus.example.test.my_event.fire_async(f=123)

    # What events were fired?
    event_messages = get_dummy_events()
    assert len(event_messages) == 2  # First is the actual event, followed by the metrics event

    # rpc_response_received
    assert event_messages[1].api_name == 'internal.metrics'
    assert event_messages[1].event_name == 'event_fired'
    assert event_messages[1].kwargs.pop('timestamp')
    assert event_messages[1].kwargs.pop('process_name')
    assert event_messages[1].kwargs == {
        'api_name': 'example.test',
        'event_name': 'my_event',
        'event_id': 'event_id',
        'kwargs': {'f': 123}
    }


@pytest.mark.run_loop
async def test_execute_events(dummy_bus: BusNode, event_consumer, get_dummy_events, mocker):
    mocker.patch.object(dummy_bus.bus_client.event_transport, '_get_fake_messages', return_value=[
        EventMessage(api_name='example.test', event_name='my_event', kwargs={'f': 123})
    ])

    # Setup the bus and do the call
    manually_set_plugins(plugins={'metrics': MetricsPlugin()})
    registry.add(TestApi())

    # The dummy transport will fire an every every 0.1 seconds
    await asyncio.sleep(0.15)

    event_messages = get_dummy_events()
    assert len(event_messages) == 2

    # before_rpc_execution
    assert event_messages[0].api_name == 'internal.metrics'
    assert event_messages[0].event_name == 'event_received'
    assert event_messages[0].kwargs.pop('timestamp')
    assert event_messages[0].kwargs.pop('process_name')
    assert event_messages[0].kwargs == {
        'api_name': 'example.test',
        'event_name': 'my_event',
        'event_id': 'event_id',
        'kwargs': {'f': 123}
    }

    # after_rpc_execution
    assert event_messages[1].api_name == 'internal.metrics'
    assert event_messages[1].event_name == 'event_processed'
    assert event_messages[1].kwargs.pop('timestamp')
    assert event_messages[1].kwargs.pop('process_name')
    assert event_messages[1].kwargs == {
        'api_name': 'example.test',
        'event_name': 'my_event',
        'event_id': 'event_id',
        'kwargs': {'f': 123}
    }
