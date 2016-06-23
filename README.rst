==========
Proxytools
==========

A command line tool for finding and testing public web proxies.

Installation
^^^^^^^^^^^^
.. code-block:: console 

   apt-get update
   apt-get install -y curl python-dev libcurl3-openssl-dev \
                      libxml2-dev libxslt1-dev \
                      zlib1g-dev libffi-dev libssl-dev
   
   
   export PYCURL_SSL_LIBRARY=openssl
   git clone https://github.com/lukemaxwell/proxytools.git
   cd proxytools
   python setup.py install
