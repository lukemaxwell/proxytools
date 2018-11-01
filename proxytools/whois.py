'''
Class for performing WHOIS lookups.
'''
import socket


class WHOISError(Exception):
    """
    Generic WHOIS lookup error.
    """
    pass


class WHOIS:
    server = 'whois.apnic.net'

    def parse_response(self, response):
        """
        Convert whois text response to dict.
        """
        data = {}
        for line in response.splitlines():
            if line.startswith('%'):
                continue
            if line.startswith(' '):
                continue
            if line == '':
                continue

            key = line.split(':')[0]
            val = line.split(':')[1].strip()
            data[key] = val

            # Cease parsing after first block
            if key == 'source':
                break

        return data

    def get(self, ip) :
        """
        Function to perform WHOIS on an IP address.

        :param ip: the ip address
        :type ip: str
        :returns: dict
        """
        #socket connection
        s = socket.socket(socket.AF_INET , socket.SOCK_STREAM)
        s.connect((self.server , 43))

        #send data
        query = ip + '\r\n'
        s.send(query.encode())

        #receive reply
        msg = ''
        while len(msg) < 10000:
            chunk = s.recv(100).decode()
            if(chunk == ''):
                break
            msg = msg + chunk

        return self.parse_response(msg)
