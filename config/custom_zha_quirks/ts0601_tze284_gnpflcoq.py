"""Tuya 4-in-1 mmWave presence sensor (TS0601 / _TZE284_gnpflcoq).

ZHA has no built-in quirk for this device, so it pairs without any useful
entity. Datapoints taken from the zigbee-herdsman-converters definition
(model "TS0601_TZE284_gnpflcoq"):

    dp 1   presence      0 = occupied (trueFalse0)
    dp 2   sensitivity   0..10
    dp 4   battery       %
    dp 7   temperature   value / 10 °C
    dp 8   humidity      %
    dp 11  illuminance   lux
    dp 102 fading_time   0..1000 s
"""

from zigpy.quirks.v2.homeassistant import UnitOfTime
from zigpy.quirks.v2.homeassistant.sensor import SensorDeviceClass
import zigpy.types as t
from zigpy.zcl.clusters.measurement import OccupancySensing

from zhaquirks.tuya import TuyaLocalCluster
from zhaquirks.tuya.builder import TuyaQuirkBuilder


class TuyaOccupancySensing(OccupancySensing, TuyaLocalCluster):
    """Tuya local OccupancySensing cluster."""


(
    TuyaQuirkBuilder("_TZE284_gnpflcoq", "TS0601")
    .adds(TuyaOccupancySensing)
    .tuya_dp(
        dp_id=1,
        ep_attribute=TuyaOccupancySensing.ep_attribute,
        attribute_name=OccupancySensing.AttributeDefs.occupancy.name,
        converter=lambda x: x == 0,
    )
    .tuya_number(
        dp_id=2,
        attribute_name="sensitivity",
        type=t.uint16_t,
        min_value=0,
        max_value=10,
        step=1,
        translation_key="sensitivity",
        fallback_name="Sensitivity",
    )
    .tuya_battery(dp_id=4, scale=2)
    .tuya_temperature(dp_id=7, scale=10)
    .tuya_humidity(dp_id=8)
    .tuya_illuminance(dp_id=11)
    .tuya_number(
        dp_id=102,
        attribute_name="fading_time",
        type=t.uint16_t,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        min_value=0,
        max_value=1000,
        step=1,
        translation_key="fading_time",
        fallback_name="Fading time",
    )
    .skip_configuration()
    .add_to_registry()
)
