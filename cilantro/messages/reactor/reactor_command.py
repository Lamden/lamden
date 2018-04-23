from cilantro.messages import MessageBase, MessageMeta
import capnp
import command_capnp


class ReactorCommand(MessageBase):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return command_capnp.ReactorCommand.from_bytes_packed(data)

    @classmethod
    def create(cls, class_name: str, func_name: str, metadata: MessageMeta=None, data: MessageBase=None, **kwargs):
        cmd = command_capnp.ReactorCommand.new_message()

        cmd.className = class_name
        cmd.funcName = func_name

        if metadata:
            assert metadata and data, "If creating command with a binary payload, " \
                                      "BOTH metadata and data must be passed in (not one or the other)"
            assert issubclass(type(data), MessageBase), "data must be a subclass of MessageBase"
            assert isinstance(metadata, MessageMeta), "Metadata must be of a MessageMeta instance"
            cmd.data = data.serialize()
            cmd.metadata = metadata.serialize()

        cmd.init('kwargs', len(kwargs))
        for i, key in enumerate(kwargs):
            cmd.kwargs[i].key, cmd.kwargs[i].value = str(key), str(kwargs[key])

        return cls.from_data(cmd)

    @property
    def class_name(self):
        return self._data.className

    @property
    def func_name(self):
        return self._data.funcName

    @property
    def data(self):
        return self._data.data

    @property
    def metadata(self):
        return self._data.metadata

    @property
    def kwargs(self):
        return {arg.key: arg.value for arg in self._data.kwargs}
