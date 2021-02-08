from abc import ABC, abstractmethod
from owrx.modes import Modes
from owrx.config import Config
from owrx.wsjt import Q65Mode, Q65Profile
from enum import Enum


class Converter(ABC):
    @abstractmethod
    def convert_to_form(self, value):
        pass

    @abstractmethod
    def convert_from_form(self, value):
        pass


class NullConverter(Converter):
    def convert_to_form(self, value):
        return value

    def convert_from_form(self, value):
        return value


class OptionalConverter(Converter):
    """
    Maps None to an empty string, and reverse
    useful for optional fields
    """

    def convert_to_form(self, value):
        return "" if value is None else value

    def convert_from_form(self, value):
        return value if value else None


class Input(ABC):
    def __init__(self, id, label, infotext=None, converter: Converter = None):
        self.id = id
        self.label = label
        self.infotext = infotext
        self.converter = self.defaultConverter() if converter is None else converter

    def defaultConverter(self):
        return NullConverter()

    def bootstrap_decorate(self, input):
        infotext = "<small>{text}</small>".format(text=self.infotext) if self.infotext else ""
        return """
            <div class="form-group row">
                <label class="col-form-label col-form-label-sm col-3" for="{id}">{label}</label>
                <div class="col-9 p-0">
                    {input}
                    {infotext}
                </div>
            </div>
        """.format(
            id=self.id, label=self.label, input=input, infotext=infotext
        )

    def input_classes(self):
        return " ".join(["form-control", "form-control-sm"])

    @abstractmethod
    def render_input(self, value):
        pass

    def render(self, config):
        value = config[self.id] if self.id in config else None
        return self.bootstrap_decorate(self.render_input(self.converter.convert_to_form(value)))

    def parse(self, data):
        return {self.id: self.converter.convert_from_form(data[self.id][0])} if self.id in data else {}


class TextInput(Input):
    def render_input(self, value):
        return """
            <input type="text" class="{classes}" id="{id}" name="{id}" placeholder="{label}" value="{value}">
        """.format(
            id=self.id, label=self.label, classes=self.input_classes(), value=value
        )


class IntConverter(Converter):
    def convert_to_form(self, value):
        return str(value)

    def convert_from_form(self, value):
        return int(value)


class NumberInput(Input):
    def __init__(self, id, label, infotext=None, append="", converter: Converter = None):
        super().__init__(id, label, infotext, converter=converter)
        self.step = None
        self.append = append

    def defaultConverter(self):
        return IntConverter()

    def render_input(self, value):
        if self.append:
            append = """
                <div class="input-group-append">
                    <span class="input-group-text">{append}</span>
                </div>
            """.format(
                append=self.append
            )
        else:
            append = ""

        return """
            <div class="input-group input-group-sm">
                <input type="number" class="{classes}" id="{id}" name="{id}" placeholder="{label}" value="{value}" {step}>
                {append}
            </div>
        """.format(
            id=self.id,
            label=self.label,
            classes=self.input_classes(),
            value=value,
            step='step="{0}"'.format(self.step) if self.step else "",
            append=append,
        )


class FloatConverter(Converter):
    def convert_to_form(self, value):
        return str(value)

    def convert_from_form(self, value):
        return float(value)


class FloatInput(NumberInput):
    def __init__(self, id, label, infotext=None, converter: Converter = None):
        super().__init__(id, label, infotext, converter=converter)
        self.step = "any"

    def defaultConverter(self):
        return FloatConverter()


class LocationInput(Input):
    def render_input(self, value):
        return """
            <div class="row">
                {inputs}
            </div>
            <div class="row">
                <div class="col map-input" data-key="{key}" for="{id}"></div>
            </div>
        """.format(
            id=self.id,
            inputs="".join(self.render_sub_input(value, id) for id in ["lat", "lon"]),
            key=Config.get()["google_maps_api_key"],
        )

    def render_sub_input(self, value, id):
        return """
            <div class="col">
                <input type="number" class="{classes}" id="{id}" name="{id}" placeholder="{label}" value="{value}" step="any">
            </div>
        """.format(
            id="{0}-{1}".format(self.id, id),
            label=self.label,
            classes=self.input_classes(),
            value=value[id],
        )

    def parse(self, data):
        return {self.id: {k: float(data["{0}-{1}".format(self.id, k)][0]) for k in ["lat", "lon"]}}


class TextAreaInput(Input):
    def render_input(self, value):
        return """
            <textarea class="{classes}" id="{id}" name="{id}" style="height:200px;">{value}</textarea>
        """.format(
            id=self.id, classes=self.input_classes(), value=value
        )


class ReceiverKeysConverter(Converter):
    def convert_to_form(self, value):
        return "\n".join(value)

    def convert_from_form(self, value):
        # \r\n or \n? this should work with both.
        return [v.strip("\r ") for v in value.split("\n")]


class CheckboxInput(Input):
    def __init__(self, id, label, checkboxText, infotext=None):
        super().__init__(id, label, infotext=infotext)
        self.checkboxText = checkboxText

    def render_input(self, value):
        return """
          <div class="{classes}">
            <input class="form-check-input" type="checkbox" id="{id}" name="{id}" {checked}>
            <label class="form-check-label" for="{id}">
              {checkboxText}
            </label>
          </div>
        """.format(
            id=self.id,
            classes=self.input_classes(),
            checked="checked" if value else "",
            checkboxText=self.checkboxText,
        )

    def input_classes(self):
        return " ".join(["form-check", "form-control-sm"])

    def parse(self, data):
        return {self.id: self.id in data and data[self.id][0] == "on"}


class Option(object):
    # used for both MultiCheckboxInput and DropdownInput
    def __init__(self, value, text):
        self.value = value
        self.text = text


class MultiCheckboxInput(Input):
    def __init__(self, id, label, options, infotext=None):
        super().__init__(id, label, infotext=infotext)
        self.options = options

    def render_input(self, value):
        return "".join(self.render_checkbox(o, value) for o in self.options)

    def checkbox_id(self, option):
        return "{0}-{1}".format(self.id, option.value)

    def render_checkbox(self, option, value):
        return """
          <div class="{classes}">
            <input class="form-check-input" type="checkbox" id="{id}" name="{id}" {checked}>
            <label class="form-check-label" for="{id}">
              {checkboxText}
            </label>
          </div>
        """.format(
            id=self.checkbox_id(option),
            classes=self.input_classes(),
            checked="checked" if option.value in value else "",
            checkboxText=option.text,
        )

    def parse(self, data):
        def in_response(option):
            boxid = self.checkbox_id(option)
            return boxid in data and data[boxid][0] == "on"

        return {self.id: [o.value for o in self.options if in_response(o)]}

    def input_classes(self):
        return " ".join(["form-check", "form-control-sm"])


class ServicesCheckboxInput(MultiCheckboxInput):
    def __init__(self, id, label, infotext=None):
        services = [Option(s.modulation, s.name) for s in Modes.getAvailableServices()]
        super().__init__(id, label, services, infotext)


class Js8ProfileCheckboxInput(MultiCheckboxInput):
    def __init__(self, id, label, infotext=None):
        profiles = [
            Option("normal", "Normal (15s, 50Hz, ~16WPM)"),
            Option("slow", "Slow (30s, 25Hz, ~8WPM"),
            Option("fast", "Fast (10s, 80Hz, ~24WPM"),
            Option("turbo", "Turbo (6s, 160Hz, ~40WPM"),
        ]
        super().__init__(id, label, profiles, infotext)


class DropdownInput(Input):
    def __init__(self, id, label, options, infotext=None, converter: Converter = None):
        try:
            isEnum = issubclass(options, DropdownEnum)
        except TypeError:
            isEnum = False
        if isEnum:
            self.options = [o.toOption() for o in options]
            if converter is None:
                converter = EnumConverter(options)
        else:
            self.options = options
        super().__init__(id, label, infotext=infotext, converter=converter)

    def render_input(self, value):
        return """
            <select class="{classes}" id="{id}" name="{id}">{options}</select>
        """.format(
            classes=self.input_classes(), id=self.id, options=self.render_options(value)
        )

    def render_options(self, value):
        options = [
            """
                <option value="{value}" {selected}>{text}</option>
            """.format(
                text=o.text,
                value=o.value,
                selected="selected" if o.value == value else "",
            )
            for o in self.options
        ]
        return "".join(options)


class Q65ModeConverter(Converter):
    def convert_to_form(self, value):
        pass

    def convert_from_form(self, value):
        pass


class Q65ModeMatrix(Input):
    def checkbox_id(self, mode, interval):
        return "{0}-{1}-{2}".format(self.id, mode.value, interval)

    def render_checkbox(self, mode, interval, value):
        return """
          <div class="{classes}">
            <input class="form-check-input" type="checkbox" id="{id}" name="{id}" {checked}>
            <label class="form-check-label" for="{id}">
              {checkboxText}
            </label>
          </div>
        """.format(
            id=self.checkbox_id(mode, interval),
            classes=self.input_classes(),
            checked="checked" if [interval, mode.name] in value else "",
            checkboxText="Mode {} interval {}s".format(mode.name, interval),
        )

    def render_input(self, value):
        checkboxes = "".join(
            self.render_checkbox(mode, interval, value)
            for interval in Q65Profile.availableIntervals
            for mode in Q65Mode
        )
        return """
            <div class="matrix q65-matrix">
                {checkboxes}
            </div>
        """.format(
            checkboxes=checkboxes
        )

    def input_classes(self):
        return " ".join(["form-check", "form-control-sm"])


class DropdownEnum(Enum):
    def toOption(self):
        return Option(self.name, str(self))


class EnumConverter(Converter):
    def __init__(self, enumCls):
        self.enumCls = enumCls

    def convert_to_form(self, value):
        return None if value is None else self.enumCls(value).name

    def convert_from_form(self, value):
        return self.enumCls[value].value


class WfmTauValues(DropdownEnum):
    TAU_50_MICRO = (50e-6, "most regions")
    TAU_75_MICRO = (75e-6, "Americas and South Korea")

    def __new__(cls, *args, **kwargs):
        value, description = args
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj

    def __str__(self):
        return "{}µs ({})".format(int(self.value * 1e6), self.description)


class AprsBeaconSymbols(DropdownEnum):
    BEACON_RECEIVE_ONLY = ("R&", "Receive only IGate")
    BEACON_HF_GATEWAY = ("/&", "HF Gateway")
    BEACON_IGATE_GENERIC = ("I&", "Igate Generic (please use more specific overlay)")
    BEACON_PSKMAIL = ("P&", "PSKmail node")
    BEACON_TX_1 = ("T&", "TX IGate with path set to 1 hop")
    BEACON_WIRES_X = ("W&", "Wires-X")
    BEACON_TX_2 = ("2&", "TX IGate with path set to 2 hops")

    def __new__(cls, *args, **kwargs):
        value, description = args
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj

    def __str__(self):
        return "{description} ({symbol})".format(description=self.description, symbol=self.value)


class AprsAntennaDirections(DropdownEnum):
    DIRECTION_OMNI = None
    DIRECTION_N = "N"
    DIRECTION_NE = "NE"
    DIRECTION_E = "E"
    DIRECTION_SE = "SE"
    DIRECTION_S = "S"
    DIRECTION_SW = "SW"
    DIRECTION_W = "W"
    DIRECTION_NW = "NW"

    def __str__(self):
        return "omnidirectional" if self.value is None else self.value
