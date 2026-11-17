# Reflection: Building a SOAP Client in Python

I started by checking the public WSDL list. Then I chose the Number Conversion Service and used zeep to generate a client from its WSDL. I turned each XML reply into a Python dataclass, added validation and custom error messages, and wrapped the client in a Flask app with GET and POST endpoints.

The biggest surprise came early. Eight of the fourteen services on the list point to NCBI's SOAP interface, which was shut down in 2015 in favor of REST. That made the REST-versus-SOAP debate feel very concrete.

My code changed as I tested it. At first, every error returned the same status code. Then I realized that bad user input (400) is different from a bad reply from the service (502), so I split them. I also rewrote one error message that showed Python's internal decimal error instead of something a user could read.

I now understand how a WSDL acts as a contract that tools can use to generate code. Next, I'd like to learn how WS-Security protects individual messages.
