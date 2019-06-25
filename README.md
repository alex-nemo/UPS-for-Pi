## UPS-for-Pi
- If you remove the power source of Raspberry Pi during operation, it is well possible that it will never boot up again, because its SD card is corrupted.
- Every  RPi must be shutdown properly to avoid the SD card corruption issues
- If RPi is powered from wall adapter and you have reliable power supply, then you can always perform shutdown before removing the power source
- But in case RPi is used in portable battery powered device then its important to monitor battery usage and perform shutdown before it runs out of juice
- My UPS is based on the following Git Repo https://github.com/craic/pi_power.git. I have modified few things as per my requirements.

## Features
- To power it up from a cold state, press a button for a few seconds
- To power it off, press the same button for a few seconds (3 seconds)
- Indicate how much power remains in the battery
- Provide an alert when that is running really low
- Shut down safely without any data corruption if the battery does run out
- To recharge the battery, just plug in a cable from a USB charger
- I have modified the shutdown code to avoide false shutdowns

## Components Used
- 1N4001 diode (https://www.thingbits.net/products/1n4001-diode-10-pack)
- 0.1uF ceramic capacitor
- 100uF electrolytic capacitor (https://www.thingbits.net/products/100uf-16v-electrolytic-capacitors-pack-of-10 )
- 10K resistor
- 100K resistor
- MCP3008 - 8-Channel 10-Bit ADC With SPI Interface (https://www.thingbits.net/products/mcp3008-8-channel-10-bit-adc-with-spi-interface)

## PCB Design
- I have desined two PCB's one for through hole componets and another for SMD compnents
- Please PCB Design folder for more details

## Soruce Code
- You can refer the original repository 'Power management for portable Raspberry Pi projects' for reference
- My code is available in 'src' folder
