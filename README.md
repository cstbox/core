# [CSTBox](http://cstbox.cstb.fr)

This repository contains the code for the core part of the CSTBox framework.

CSTBox is a soft real-time toolkit for building component-oriented embedded systems. 
It has been created for developping autonomous applications based on heterogeneous 
sensors and actuators networks. It is not just yet another data logger, but provides
the required infrastructure to add your own specific in-situ processing, and obtain
a fully autonomous system, not required connection to a server for remote processing.

It has been created and is maintained by [Eric Pascual](https://github.com/ericpascual) 
and [Daniel Cheung](https://github.com/daniel-cheung).

To get started, checkout [http://cstbox.cstb.fr](http://cstbox.cstb.fr)!

## Runtime dependencies

CSTBox relies on D-Bus for inter-components communication. On Debian based target systems,
required packages can be installed by :

    sudo apt-get install dbus-x11 python-gobject

