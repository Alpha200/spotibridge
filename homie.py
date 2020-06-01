import weakref
from enum import Enum
from typing import Optional, Dict, Set, Any, Protocol, NamedTuple, List, Tuple, Union

from packaging.version import Version, InvalidVersion

from logger import get_logger

HOMIE_PREFIX = "homie"


class HomieState(Enum):
    INIT = "init"
    READY = "ready"
    DISCONNECTED = "disconnected"
    SLEEPING = "sleeping"
    LOST = "lost"
    ALERT = "alert"


class HomieDataType(Enum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    ENUM = "enum"
    COLOR = "color"


class HomieExtension(NamedTuple):
    extension_id: str
    extension_version: Version
    supported_homie_versions: List[str]

    def __str__(self) -> str:
        return f"{self.extension_id}:{self.extension_version}:[{';'.join(self.supported_homie_versions)}]"


class HomieProperty:
    def __init__(self, property_id: str, parent_node: "HomieNode", valid: bool = False):
        self.parent_node = weakref.proxy(parent_node)
        self.property_id = property_id
        self.name: Optional[str] = None
        self.datatype: Optional[HomieDataType] = None
        self.format: Optional[str] = None
        self.unit: Optional[str] = None
        self.retained = True
        self.settable = False
        self._value: Optional[Union[int, float, bool, str, Tuple[int, int, int]]] = None
        self.additional_attributes: Dict[str, Any] = {}
        self.__observers: Set[HomiePropertyObserver] = set()
        parent_node.properties[property_id] = self

        if valid:
            if parent_node.valid_properties is None:
                parent_node.valid_properties = set()

            parent_node.valid_properties.add(property_id)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        previous_value = self.value
        self._value = value

        for observer in self.__observers:
            observer.homie_property_updated(self, previous_value)

    def add_observer(self, observer: "HomiePropertyObserver"):
        self.__observers.add(observer)

    def remove_observer(self, observer: "HomiePropertyObserver"):
        self.__observers.remove(observer)

    def formatted_value(self):
        if self._value is None:
            return None

        if (
            self.datatype is None
            or self.datatype == HomieDataType.INTEGER
            or self.datatype == HomieDataType.FLOAT
        ):
            return str(self._value)

        if self.datatype == HomieDataType.STRING or self.datatype == HomieDataType.ENUM:
            return self._value

        if self.datatype == HomieDataType.COLOR:
            return ",".join(str(val) for val in self._value)

        if self.datatype == HomieDataType.BOOLEAN:
            return "true" if self._value else "false"

    def publish_value(self):
        parent_node = self.parent_node
        parent_device = parent_node.parent_device

        parent_device.mqtt_client.publish(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}",
            self.formatted_value(),
            retain=self.retained,
            qos=1,
        )

    def publish_config(self):
        parent_node = self.parent_node
        parent_device = parent_node.parent_device

        parent_device.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}/$name",
            self.name,
        )
        parent_device.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}/$datatype",
            self.datatype.value,
        )
        parent_device.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}/$format",
            self.format,
        )
        parent_device.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}/$unit",
            self.unit,
        )
        parent_device.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}/$retained",
            "true" if self.retained else "false",
        )
        parent_device.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent_device.device_id}/{parent_node.node_id}/{self.property_id}/$settable",
            "true" if self.settable else "false",
        )
        self.publish_value()

        # TODO: Publish additional attributes?

    def __repr__(self):
        return f"{{HomieProperty: {self.property_id}}}"


class MqttClient(Protocol):
    def publish(
        self, topic: str, payload: Optional[str], retain: bool = False, qos: int = 0
    ):
        ...


class InvalidConfigurationError(Exception):
    """Raised when the device configuration is invalid unexpectedly"""

    pass


class HomieNode:
    def __init__(self, node_id: str, parent_device: "HomieDevice", valid: bool = False):
        self.parent_device = weakref.proxy(parent_device)
        self.node_id = node_id
        self.name: Optional[str] = None
        self.type: Optional[str] = None
        self.valid_properties: Optional[Set[str]] = None
        self.properties: Dict[str, HomieProperty] = {}
        self.additional_attributes: Dict[str, Any] = {}
        parent_device.nodes[node_id] = self

        if valid:
            if parent_device.valid_nodes is None:
                parent_device.valid_nodes = set()

            parent_device.valid_nodes.add(node_id)

    def publish_config(self):
        parent = self.parent_device
        parent.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent.device_id}/{self.node_id}/$name", self.name
        )
        parent.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent.device_id}/{self.node_id}/$type", self.type
        )
        parent.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{parent.device_id}/{self.node_id}/$properties",
            ",".join(self.valid_properties),
        )

        # TODO: Publish additional attributes?

        for property_id in self.valid_properties:
            self.properties[property_id].publish_config()

    def __repr__(self):
        return f"{{HomieNode: {self.node_id}}}"


class HomieDevice:
    def __init__(self, device_id: str, mqtt_client: MqttClient):
        self.mqtt_client = weakref.proxy(mqtt_client)
        self.name: Optional[str] = None
        self.device_id = device_id
        self.version: Optional[Version] = None
        self.state: Optional[HomieState] = None
        self.extensions: Optional[Set[HomieExtension]] = None
        self.implementation: Optional[str] = None
        self.valid_nodes: Optional[Set[str]] = None
        self.nodes: Dict[str, HomieNode] = {}
        self.additional_attributes: Dict[str, Any] = {}
        self.is_valid = False

    def validate(self) -> bool:
        self.is_valid = self.__validate()
        return self.is_valid

    def __validate(self) -> bool:
        if (
            self.name is None
            or self.version is None
            or self.extensions is None
            or self.valid_nodes is None
        ):
            return False

        # Filter gathered nodes
        self.nodes = {k: v for k, v in self.nodes.items() if k in self.valid_nodes}

        if self.valid_nodes != self.nodes.keys():
            # Required nodes are missing
            return False

        for node in self.nodes.values():
            if node.name is None or node.type is None or node.valid_properties is None:
                return False

            node.properties = {
                k: v for k, v in node.properties.items() if k in node.valid_properties
            }

            if node.valid_properties != node.properties.keys():
                # Required properties are missing
                return False

            for node_property in node.properties.values():
                if node_property.name is None or node_property.datatype is None:
                    return False

        return True

    def publish_qos1_retained(self, topic: str, payload: Optional[str]):
        self.mqtt_client.publish(topic, payload, retain=True, qos=1)

    def publish_config(self):
        if not self.validate():
            raise InvalidConfigurationError()

        self.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{self.device_id}/$state", HomieState.INIT.value
        )

        self.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{self.device_id}/$homie", str(self.version)
        )
        self.publish_qos1_retained(f"{HOMIE_PREFIX}/{self.device_id}/$name", self.name)
        self.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{self.device_id}/$extensions",
            ",".join(str(extension) for extension in self.extensions),
        )
        self.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{self.device_id}/$implementation", self.implementation
        )

        self.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{self.device_id}/$nodes", ",".join(self.valid_nodes)
        )

        # TODO: Publish additional attributes?

        for node_id in self.valid_nodes:
            self.nodes[node_id].publish_config()

        self.publish_qos1_retained(
            f"{HOMIE_PREFIX}/{self.device_id}/$state", HomieState.READY.value
        )
        self.state = HomieState.READY

    def __repr__(self):
        return f"{{HomieDevice: {self.device_id}}}"


class HomieManagerDelegate(Protocol):
    def on_validated_homie_device(self, device: HomieDevice) -> None:
        ...


class HomiePropertyObserver(Protocol):
    def homie_property_updated(
        self,
        homie_property: HomieProperty,
        previous_value: Union[int, float, bool, str, Tuple[int, int, int]],
    ):
        ...


def add_additional_attribute(
    attribute_dict: Dict[str, Any], remaining_levels: List[str], payload: Optional[str]
):
    if len(remaining_levels) > 1:
        if remaining_levels[0] not in attribute_dict:
            current_level = {}
        else:
            current_level = attribute_dict[remaining_levels[0]]

        add_additional_attribute(current_level, remaining_levels[1:], payload)
    else:
        attribute_dict[remaining_levels[0]] = payload


class HomieManager:
    def __init__(
        self, mqtt_client: MqttClient, delegate: Optional[HomieManagerDelegate] = None
    ):
        self.homie_devices: Dict[str, HomieDevice] = {}
        self.logger = get_logger("HomieManager")
        self.mqtt_client = mqtt_client

        if delegate is not None:
            self.delegate = weakref.proxy(delegate)
        else:
            self.delegate = None

    def parse_with_datatype(self, datatype: HomieDataType, payload: str):
        try:
            if datatype == HomieDataType.INTEGER:
                return int(payload)
            elif datatype == HomieDataType.FLOAT:
                return float(payload)
            elif datatype == HomieDataType.BOOLEAN:
                return payload == "true"
            elif datatype == HomieDataType.COLOR:
                color_tuple = tuple([int(v) for v in payload.split(",")])

                if len(color_tuple) != 3:
                    raise ValueError()

                return color_tuple
            elif datatype == HomieDataType.STRING:
                return payload
            elif datatype == HomieDataType.ENUM:
                return payload
        except ValueError:
            self.logger.error(f"Failed to parse payload for datatype {datatype.name}")

        return None

    def on_homie_message(self, topic: str, payload: Optional[str], retained: bool):
        topic_levels = topic.split("/")
        number_of_levels = len(topic_levels)

        if number_of_levels > 1 and topic_levels[1] == "$broadcast":
            # Ignore broadcasts
            return

        if number_of_levels < 3:
            self.logger.warn(
                f"Could not parse incoming homie message for topic {topic}"
            )
            return

        if topic_levels[1] == "homelocator":
            if number_of_levels != 5 or topic_levels[4] != "set":
                # Ignore all messages that are not set
                return

            # TODO: Received set for homelocator property of own device (But currently nothing is settable)
            return

        device_id = topic_levels[1]

        if device_id not in self.homie_devices:
            device = HomieDevice(device_id, self.mqtt_client)
            self.homie_devices[device_id] = device
        else:
            device = self.homie_devices[device_id]

        if number_of_levels == 3:
            level_str = topic_levels[2]

            if level_str == "$homie":
                try:
                    device.version = Version(payload)
                except InvalidVersion:
                    self.logger.error("Failed to parse homie version")
            elif level_str == "$name":
                device.name = payload
            elif level_str == "$extensions":
                if payload is not None:
                    device.extensions = set()
                    extensions = payload.split(",")

                    for extension in extensions:
                        splitted = extension.split(":")

                        if len(splitted) != 3:
                            self.logger.warn("Failed to parse homie extension!")
                            return

                        try:
                            extension_version = Version(splitted[1])
                        except InvalidVersion:
                            self.logger.error("Failed to parse extension version")
                            return

                        homie_versions = splitted[3]

                        if homie_versions[0] != "[" or homie_versions[-1] != "]":
                            self.logger.error("Invalid supported homie versions")
                            return

                        homie_versions = homie_versions[1:-1].split(";")

                        device.extensions.add(
                            HomieExtension(
                                extension_id=splitted[0],
                                extension_version=extension_version,
                                supported_homie_versions=homie_versions,
                            )
                        )
            elif level_str == "$nodes":
                if payload is not None:
                    device.valid_nodes = set(payload.split(","))
            elif level_str == "$implementation":
                device.implementation = payload
            elif level_str == "$state":
                # TODO: Validate changes after delay, so remaining messages for configuration can come in in time
                try:
                    device.state = HomieState(payload)

                    if device.state == HomieState.READY:
                        if device.validate():
                            # Device has been validated
                            if self.delegate is not None:
                                try:
                                    self.delegate().on_validated_homie_device(device)
                                except ReferenceError:
                                    self.delegate = None

                except ValueError:
                    self.logger.error(
                        f"Failed to parse homie state for device {device_id}"
                    )
            else:
                if level_str.startswith("$"):
                    # Must be an extension attribute
                    device.additional_attributes[level_str] = payload
                else:
                    self.logger.warn("Received unknown homie message")
        elif number_of_levels > 3:
            node_id = topic_levels[2]

            if node_id.startswith("$"):
                # This must be an device attribute of an extension
                add_additional_attribute(
                    device.additional_attributes, topic_levels[2:], payload
                )
                return

            if node_id not in device.nodes:
                node = HomieNode(node_id, device)
                device.nodes[node_id] = node
            else:
                node = device.nodes[node_id]

            if number_of_levels == 4:
                level_str = topic_levels[3]

                if level_str == "$name":
                    node.name = payload
                elif level_str == "$type":
                    node.type = payload
                elif level_str == "$properties":
                    if payload is not None:
                        node.valid_properties = set(payload.split(","))
                else:
                    if level_str.startswith("$"):
                        # Must be a homie extension atttribute
                        node.additional_attributes[level_str] = payload
                        return
                    else:
                        property_id = level_str

                        if property_id not in node.properties:
                            homie_property = HomieProperty(property_id, node)
                            node.properties[property_id] = homie_property
                        else:
                            homie_property = node.properties[property_id]

                        if payload is None:
                            homie_property.value = None
                        else:
                            if homie_property.datatype is not None:
                                homie_property.value = self.parse_with_datatype(
                                    homie_property.datatype, payload
                                )
                            else:
                                homie_property.raw_value = payload
            elif number_of_levels >= 5:
                property_id = topic_levels[3]

                if property_id.startswith("$"):
                    add_additional_attribute(
                        node.additional_attributes, topic_levels[2:], payload
                    )
                    return

                if property_id not in node.properties:
                    homie_property = HomieProperty(property_id, node)
                    node.properties[property_id] = homie_property
                else:
                    homie_property = node.properties[property_id]

                level_str = topic_levels[4]

                if level_str == "$name":
                    homie_property.name = payload
                elif level_str == "$datatype":
                    try:
                        homie_property.datatype = HomieDataType(payload)

                        if homie_property.raw_value is not None:
                            homie_property.value = self.parse_with_datatype(
                                homie_property.datatype, homie_property.raw_value
                            )
                            homie_property.raw_value = None
                    except ValueError as ex:
                        self.logger.error(
                            f"Failed to parse homie property data type: {ex}"
                        )
                elif level_str == "$settable":
                    homie_property.settable = payload == "true"
                elif level_str == "$retained":
                    homie_property.retained = payload == "true"
                elif level_str == "$unit":
                    homie_property.unit = payload
                elif level_str == "$format":
                    homie_property.format = payload
                elif level_str == "set":
                    # Ignore sets for other devices
                    pass
                else:
                    if level_str.startswith("$"):
                        add_additional_attribute(
                            homie_property.additional_attributes,
                            topic_levels[4:],
                            payload,
                        )
                    else:
                        self.logger.warn("Received unknown homie message")
