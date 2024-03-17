# sca_guide

This simple Python application is used as a helper for CIS guidelines used by Wazuh Security Configuration Assessment (SCA).

## How it works

The pronciple behind is that one must stick to a hardening guide, then should analyze the requirements in order to create a list of loosening factors. Every environment is different, and every environment must stick to a baseline. A loosening guide is better than a custom made hardening guide in most cases.

Here, the simple terminal application asks each requirement one by one, and if you want to add an exception, you must specify a justification. Therefore, you have a list of exceptions documented for you.

```bash
usage: sca_guide.py [-h] [--baseline BASELINE] [--custom CUSTOM] [--loosening LOOSENING]

scaGuide (0.1) is a demo application.

options:
  -h, --help            show this help message and exit
  --baseline BASELINE, -b BASELINE
                        Path to the Wazuh SCA file to start with
  --custom CUSTOM, -c CUSTOM
                        Path to the custom Wazuh SCA file to save
  --loosening LOOSENING, -l LOOSENING
                        Path to the list of suppression decisions from the Wazuh SCA file
```

## Installation

Use either `pip install -r requirements.txt` or `pip install -r requirements.dev.txt` if you want to develop the code.

## What is next?

When you have a custom SCA file created, follow [Wazuh documentation](https://documentation.wazuh.com/current/user-manual/capabilities/sec-config-assessment/creating-custom-policies.html).

It is better to store the loosening file next to it as a helper, and in whatever documentation tool or source code repository you use in your team.
