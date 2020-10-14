from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from uuid import uuid4
from time import sleep
import ESL
import json
import logging

logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%b %d %H:%M:%S',
        filename='app.log',
        level=logging.DEBUG
)
logger = logging.getLogger()


class EventHandler:
    def __init__(self, socket, esl, event: ESL.ESLevent, context=None):
        self.esl = esl
        self.socket = socket
        self.event = json.loads(event.serialize('json'))
        self.context = context or {}

    def process(self):
        func = getattr(self, self.event['Event-Name'], None)
        if func:
            func()

    def CHANNEL_CREATE(self):
        logger.debug('Processing CHANNEL_CREATE')
        self.esl.execute("info", "Hello World", self.event['Unique-ID'])

    def CHANNEL_HANGUP_COMPLETE(self):
        if self.event['Unique-ID'] in self.context['root_channels']:
            self.socket.loseConnection()
            self.context['root_channels'].remove(self.event['Unique-ID'])
        logger.debug('Processing CHANNEL_HANGUP_COMPLETE')


class Dialplan:
    def __init__(self, esl, info: ESL.ESLevent):
        self.esl = esl
        self.info = json.loads(info.serialize('json'))
        self.context = {}

    def process(self):
        func = getattr(self, self.info['Channel-Context'], None)
        if func:
            func()

    def inbound_sudonum(self):
        new_channel_uuid = str(uuid4())
        logger.debug('new_channel_uuid: %s', new_channel_uuid)
        # esl.filter('Unique-ID', new_channel_uuid)
        # esl.events('json', 'all')
        self.esl.execute(
            'bridge',
            '{ignore_early_media=true}sofia/gateway/outbound/%s' % (
                self.info['Caller-Destination-Number']
            ),
            self.info['Unique-ID']
        )


class LoggingProtocol(LineReceiver):
    MAX_LENGTH = 2**16
    line_mode = 1
    delimiter = b'\n\n'
    root_channels = []

    def lineLengthExceeded(self, line):
        logger.debug('Exceeded limit')

    def lineReceived(self, byte):
        try:
            event = ESL.ESLevent('json', byte[byte.index(b'{'):].decode())
            if not event:
                raise ValueError('No event')
            event_name = event.getHeader('Event-Name')
            if not event_name:
                raise ValueError('No event name')
        except ValueError:
            logger.debug(byte)
            return

        logger.debug('Event:%s, uuid: %s' % (event_name, event.getHeader('Unique-ID')))
        context = dict(**self.context, root_channels=self.root_channels)
        handler = EventHandler(self.transport, self.esl, event, context=context)
        handler.process()

    def connectionMade(self):
        self.fd = self.transport.getHandle().fileno()
        logger.debug('Connected to : %s', self.fd)
        self.esl = ESL.ESLconnection(self.fd)
        self.esl.events('json', 'all')
        self.esl.sendRecv('linger')
        if self.esl.connected():
            info = self.esl.getInfo()
            uuid = info.getHeader("unique-id")
            self.root_channels.append(uuid)
            logger.debug(self.root_channels)
            dialplan = Dialplan(self.esl, info)
            dialplan.process()
            self.context = dialplan.context

    def connectionLost(self, reason):
        logger.debug(f'Disconnect: {self.fd}, reason: {reason}')


class LogfileFactory(Factory):

    protocol = LoggingProtocol

    def __init__(self, fileName):
        self.file = fileName

    def startFactory(self):
        self.fp = open(self.file, 'a')

    def stopFactory(self):
        self.fp.close()


reactor.listenTCP(8040, LogfileFactory('file.log'))
reactor.run()
