# Home Assistant - Grohe Smarthome (Sense and Blue)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

Grohe Smarthome (Sense and Blue) integration for Home Assistant
 
This is an integration for all the Grohe Smarthome devices into Home Assistant. Namely, these are:
 - **Grohe Sense** (small leak sensor)
 - **Grohe Sense Guard** (main water pipe sensor/breaker)
 - **Grohe Blue Home** (water filter with carbonation)
 - **Grohe Blue Professional** (water filter with carbonation)

## Disclaimer
The authors of this integration are not affiliated with Grohe or the Grohe app in any way. The project depends on the undocumented and unofficial Grohe API. If Grohe decides to change the API in any way, this could break the integration. Even tough the integration was tested on several devices without problems, the authors are not liable for any potential issues, malfunctions or damages arising from using this integration. 
Use at your own risk!

## Getting started
If you're new, take a look at the Installation Guide here: [Getting Started](https://github.com/Flo-Schilli/ha-grohe_smarthome/wiki/Getting-Started)

Other documentation for available actions, device sensors, notifications, etc. can be found in the [wiki](https://github.com/Flo-Schilli/ha-grohe_smarthome/wiki)

## Remarks on the "API"
I have not seen any documentation from Grohe on the API this integration is using, so likely it was only intended for their app.
Breaking changes have happened previously, and can easily happen again.
I try to always keep the integration updated to their latest API.

The API returns _much_ more detailed data than is exposed via these sensors.
For withdrawals, it returns an exact start- and end time for each withdrawal, as well as volume withdrawn.
It seems to store data since the water meter was installed, so you can extract a lot of historic data (but then polling gets a bit slow).
I'm not aware of any good way to expose time series data like this in home assistant (suddenly I learn that 2 liters was withdrawn 5 minutes ago, and 5 liters was withdrawn 2 minutes ago).
If anyone has any good ideas/pointers, that'd be appreciated.

## Credits
Thanks to:
 - [gkreitz](https://github.com/gkreitz/homeassistant-grohe_sense) for the initial implementation of the Grohe Sense
 - [rama1981](https://github.com/rama1981) for reaching out and going through the trial and error for the Grohe Blue Professional.
 - [daxyorg](https://github.com/daxyorg) for going through the trial and error of the refactored version and testing with Grohe Blue Home.
 - [windkh](https://github.com/windkh/node-red-contrib-grohe-sense) from whom I've token a lot of the notification types available.
 - [FlorianSW](https://github.com/FlorianSW/grohe-ondus-api-java) for the initial protocol understanding
