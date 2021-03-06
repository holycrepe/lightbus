from typing import Dict

from lightbus.exceptions import UnknownApi, InvalidApiRegistryEntry, EventNotFound, MisconfiguredApiOptions

__all__ = ['Api', 'Event']


class Registry(object):
    def __init__(self):
        self._apis: Dict[str, Api] = dict()

    def add(self, api: 'Api'):
        if isinstance(api, type):
            raise InvalidApiRegistryEntry(
                "An attempt was made to add a type to the API registry. This "
                "is probably because you are trying to add the API class, rather "
                "than an instance of the API class."
            )

        self._apis[api.meta.name] = api

    def get(self, name) -> 'Api':
        try:
            return self._apis[name]
        except KeyError:
            raise UnknownApi(
                "An API named '{}' was requested from the registry but the "
                "registry does not recognise it. Maybe the incorrect API name "
                "was specified, or maybe the API has not been registered.".format(name)
            )

    def public(self):
        return [api for api in self._apis.values() if not api.meta.internal]

    def internal(self):
        return [api for api in self._apis.values() if api.meta.internal]

    def all(self):
        return self._apis.values()


registry = Registry()


class ApiOptions(object):
    name: str
    internal: bool = False
    auto_register: bool = True

    def __init__(self, options):
        for k, v in options.items():
            if not k.startswith('_'):
                setattr(self, k, v)


class ApiMetaclass(type):

    def __init__(cls, name, bases=None, dict=None):
        is_api_base_class = (name == 'Api' and bases == (object,))
        if is_api_base_class:
            super(ApiMetaclass, cls).__init__(name, bases, dict)
        else:
            options = dict.get('Meta', None)
            if options is None:
                raise MisconfiguredApiOptions(
                    "API class {} does not contain a class named 'Meta'. Each API definition "
                    "must contain a child class named 'Meta' which can contain configurations options. "
                    "For example, the 'name' option is required and specifies "
                    "the name used to access the API on the bus."
                    "".format(name)
                )
            cls.sanity_check_options(name, options)
            cls.meta = ApiOptions(cls.Meta.__dict__.copy())
            super(ApiMetaclass, cls).__init__(name, bases, dict)

            if cls.meta.auto_register:
                registry.add(cls())

    def sanity_check_options(cls, name, options):
        if not getattr(options, 'name', None):
            raise MisconfiguredApiOptions(
                "API class {} does not specify a name option with its "
                "'Meta' options."
                "".format(name)
            )


class Api(object, metaclass=ApiMetaclass):

    class Meta:
        name = None

    async def call(self, procedure_name, kwargs):
        # TODO: Handling code for sync/async method calls (if we want to support both)
        return getattr(self, procedure_name)(**kwargs)

    def get_event(self, name) -> 'Event':
        event = getattr(self, name, None)
        if isinstance(event, Event):
            return event
        else:
            raise EventNotFound("Event named {}.{} could not be found".format(self, name))

    def __str__(self):
        return self.meta.name


class Event(object):

    def __init__(self, arguments):
        # Ensure you update the __copy__() method if adding instance variables below
        self.arguments = arguments
