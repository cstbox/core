# CSTBox core

This repository contains the code for the core part of the [CSTBox framework](http://cstbox.github.io).

CSTBox is a soft real-time toolkit for building component-oriented embedded systems. 
It has been created for developping autonomous applications based on heterogeneous 
sensors and actuators networks. It is not just yet another data logger, but provides
the required infrastructure to add your own specific in-situ processing, and obtain
a fully autonomous system, not requiring a connection to a server for remote processing.

It has been created and is maintained by [Eric Pascual](https://github.com/ericpascual) 
and [Daniel Cheung](https://github.com/daniel-cheung).

To get started, please checkout [the project web site](http://cstbox.github.io)!

## Installation

### Some preliminary background

Current works are made in Debian based distributions context. We use a bare Ubuntu Server
12.04 LTS for our deployments on i386 targets, installing nothing else but the `ssh` server. Raspberry
deployements use a Raspbian where X server has been disabled.

If you are using a different option, you will have to adapt to your target, including migrating
services to the init mechanism used by your system. 

Installation adds the appropriate configuration for `logrotate`. If your target does not include it,
either add it if possible, or use some custom mechanism for limiting the log files size. 
At the worst you can modify the service starting scripts to redirect logs to `dev/null`, but you will
be left without any way to investigate problems which could arise.

Please, don't ask us how to do for deploying on a Windows box,
since we will never care about this option. We don't consider Windows to be eligible for 
an embedded headless system.
 
### Installing with `apt-get`

**WARNING** - PPA server is not yet available

Add the CSTBox PPA to the sources list once for all :

    deb http://to.be.defined.url/ ./

You will then be able to install the CSTBox core using : 

    $ sudo apt-get install cstbox-core
    
Required dependencies will be installed automatically if needed. Pay attention to the suggested 
packages. Most of the time they can be useful.

### Installing with `dpkg`

Dependencies must be installed by hand before the CSTBox package :

    $ sudo apt-get install dbus-x11 python-gobject python-gobject-2
    $ sudo dpkg -i cstbox-core_<version>_all.deb
