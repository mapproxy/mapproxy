#create a tunnel
ssh -nNT -R bogosoft.com:8080:localhost:5050 bogosoft.com

#start server
proxy_manager.py -f tests/cite/cite.yaml run --threaded

#tests
http://cite.opengeospatial.org/teamengine