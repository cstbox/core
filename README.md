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

Current works are made in Debian based distributions context. We currently use a bare Ubuntu Server
12.04 LTS for our deployments on i386 targets, installing nothing else but the ssh server. Raspberry
deployements use a Raspbian which X server is disabled.

### With `apt-get`

**WARNING** - PPA server is not yet available

Add the CSTBox PPA to the sources list once for all :

    deb http://to.be.defined.url/ ./

You will then be able to install the CSTBox core using : 

    $ sudo apt-get install cstbox-core
    
Required dependencies will be installed automatically if needed. 

Pay attention to the suggested packages. Most of the time it can be usefull to add them.

### With `dpkg`

Dependencies must be installed by hand before the CSTBox package :

    $ sudo apt-get install dbus-x11 python-gobject python-gobject-2
    $ sudo dpkg -i cstbox-core_<version>_all.deb
