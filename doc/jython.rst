MapProxy for Jython
===================

.. warning:: MapProxy for Jython and this document is not stable.

This document shall help you to install/deploy the `MapProxy` with an Apache-Tomcat-Server.

Requirements
------------
1. Java
In order to get things work, the minimum Java version required is 1.5. You can check your Java version, just open the console and type ``java -version``. If you have an older version of Java installed or don't have Java installed at all, please download and install Java SE at http://java.sun.com.

2. Tomcat Apache Server
If you already have a Tomcat-Server installed, skip this point and continue with point two.
The .war-file needs to be deployed via a Tomcat Apache Server. Please visit http://tomcat.apache.org and download a `Tomcat-Server` depending on your Java version, e.g. Tomcat Apache version 6.x requires Java version 1.5 or higher.    
    
3. Jython
The last requirement is Jython, which you can download at http://www.jython.com.
`JMapProxy` has been tested with Jython version 2.5.2, so be sure to get this one.
After downloading it, you should create a folder named ``jython2.5.2`` anywhere on your drive and install Jython there.


Deploying the .WAR file
-----------------------
After installing Java, Tomcat and Jython, copy the ``MapProxy.war``, which is in the same folder like this document, go to ``$TOMCAT_HOME/webapps/`` and paste the file.
(Of course, you can also copy/paste the file via the command-line ``cp mapproxy.war $TOMCAT_HOME/webapps/``) 

You can either unzip the .WAR file now or start your Tomcat Server.
If you don't know how to start the server, open your console and type ``$TOMCAT_HOME/bin/catalina.sh run```

Now you should see a folder named ``MapProxy`` at ``$TOMCAT_HOME/webapps/``.


Configure the `Mapproxy`
------------------------
The configuration file of `MapProxy` is located at ``$TOMCAT_HOME/webapps/MapProxy/WEB-INF/etc/mapproxy.yaml``
Open this file with any text-editor and configure the `MapProxy` according to your needs.
For further informations, please read :doc:`configuration`

All you need to do now is to start/restart the Tomcat-Server.


Exceptions/Bugs
---------------
If you experience other errors or bugs, please report them to us.
