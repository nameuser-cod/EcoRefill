# Test the 1 kg HX711 scale on Raspberry Pi 5

Copy `check_weight.py` to the Pi's `ecorefill-pi` directory. This standalone
diagnostic uses DT on GPIO 5 (physical pin 29), SCK on GPIO 6 (pin 31),
3.3 V on pin 1, and GND on pin 6. Follow the HX711's printed labels.
Only one program should use these two signal pins at a time.

On Raspberry Pi OS, install the GPIO dependency and run from that directory:

```bash
sudo apt update
sudo apt install python3-lgpio
/usr/bin/python3 check_weight.py
```

The script identifies the Pi 5 RP1 chip by its label, because its device number
varies across kernel versions. Using the system Python above makes the apt
package available even if your application uses a virtual environment.

Place a light object on the platform, then remove it. Raw counts should change
and return near their original value. Negative raw counts are normal. These
numbers are not grams. Press Ctrl+C to stop.

Next, use a known mass, such as a 100 g calibration weight:

```bash
/usr/bin/python3 check_weight.py --calibrate
```

Follow the prompts to measure the empty platform and the known mass. The script
prints the offset and signed counts-per-gram factor, then displays grams.
Calibration lasts only for that run; save the printed numbers for later setup.
Remove the reference mass and verify near-zero readings, then check with a
different known mass. Displaying tenths of a gram does not establish accuracy.
The total supported load, including platform and container, must stay within
1 kg. Taring does not increase the load cell's capacity.

If readings time out, check power, common ground, and DT/SCK labels. If DT stays
low or the ADC saturates, check the load-cell connections and mounting. If the
clock timing check fails, stop CPU-heavy programs and rerun. Python on Linux
cannot guarantee HX711 pulse timing; this diagnostic stops on detected timing
violations rather than displaying that sample. Persistent failures need a
different acquisition method before integration into the running machine.

This tool does not yet supply weight to EcoRefill's inspection or reward flow.
Validate actual readings and calibration before adding acceptance thresholds.

References: [HX711 datasheet](https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf),
[lgpio Python API source](https://github.com/joan2937/lg/blob/master/PY_LGPIO/lgpio_extra.py),
[Raspberry Pi GPIO guidance](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-006553-WP/A-history-of-GPIO-usage-on-Raspberry-Pi-devices-and-current-best-practices).
