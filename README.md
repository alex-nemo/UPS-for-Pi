# UPS-for-Pi
- If you remove the power source of Raspberry Pi during operation, it is well possible that it will never boot up again, because its SD card is corrupted.
- Every  RPi must be shutdown properly to avoid the SD card corruption issues
- If RPi is powered from wall adapter and you have reliable power supply, then you can always perform shutdown before removing the power source
- But in case RPi is used in portable battery powered device then its important to monitor battery usage and perform shutdown before it runs out of juice
- My UPS is based on the following Git Repo https://github.com/craic/pi_power.git. I have modified few things as per my requirements.
