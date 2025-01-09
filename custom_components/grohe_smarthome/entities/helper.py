import logging
from enum import Enum
from typing import List, Type

from homeassistant.components.valve import ValveEntityFeature
from homeassistant.const import UnitOfTemperature, PERCENTAGE, UnitOfVolume, UnitOfVolumeFlowRate, UnitOfPressure, \
    UnitOfTime

from custom_components.grohe_smarthome.enums.grohe_enums import GroheBlueFilterType

_LOGGER = logging.getLogger(__name__)

class Helper:
    @staticmethod
    def get_ha_units(unit: str) -> str:
        if unit == 'Celsius':
            return UnitOfTemperature.CELSIUS
        elif unit == 'Percentage':
            return PERCENTAGE
        elif unit == 'Liters':
            return UnitOfVolume.LITERS
        elif unit == 'Cubic meters':
            return UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
        elif unit == 'Bar':
            return UnitOfPressure.BAR
        elif unit == 'Minutes':
            return UnitOfTime.MINUTES
        else:
            return unit

    @staticmethod
    def get_valve_features(features: List[str]) -> int:
        parsed_features: List[Type[ValveEntityFeature]] = []
        for feature in features:
            try:
                parsed = ValveEntityFeature[feature.upper()]
                parsed_features.append(parsed)
            except ValueError:
                _LOGGER.error(f'Provided feature {feature} is not a valid ValveEntityFeature from HA')

        bit_features = 0
        for parsed_feature in parsed_features:
            bit_features |= parsed_feature.value

        return bit_features

    @staticmethod
    def get_config_enum(enum_name: str) -> Type[Enum]:
        if enum_name == 'GroheBlueFilterType':
            return GroheBlueFilterType
