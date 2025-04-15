convert-to-pdf server
=====================
Using LibreOffice as a server for converting documents to pdf

This repository was forked from the UnoServer repository with the bellow main changes:

1. Simplified the class that manages the libreoffice process and wraps the Uno bindings for conversion.
2. Removed the XMLRPC server functionality.
3. Added better control and healthchecks over the libreoffice process
4. Added RESTful interface via Flask
5. Added a Dockerfile to create a consistent working image.
6. Removed redundant components and files.

There are two endpoints:

1. `http://<host>:<port>/convert-to-pdf`
2. `http://<host>:<port>/heartbeat`

For example usage, please view `tests/client.py`

For possible environment configuration, please view the `.env.example` file.