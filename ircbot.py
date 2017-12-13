#!/usr/bin/env python
import sys

from linkresolver import LinkResolver
from watchfourchan import WatchFourChan
from watchhackernews import WatchHackerNews
from watcheightchan import WatchEightChan
from watchreddit import WatchReddit
from watchpastebin import WatchPasteBin
from quote import Quote

from re import findall
from circuits import Debugger
from circuits import Component
from circuits.net.sockets import TCPClient, connect
from circuits.protocols.irc import IRC, PRIVMSG, USER, NICK, JOIN, PART
from circuits.protocols.irc import ERR_NICKNAMEINUSE
from circuits.protocols.irc import RPL_ENDOFMOTD, ERR_NOMOTD

"""
A few small commands that are really a part of the bot itself and don't deserve
a file to themselves
"""

class Source():
    def execute(self, keywords, target, source, ircbot):
        ircbot.fire(PRIVMSG(target, "Source available here: https://github.com/Astonex/IRC-Bot/"))

    def usage(self):
        pass

class Allow():
    def __init__(self):
        self.whitelist = []

    def execute(self, keywords, target, source, ircbot):
        if len(keywords) != 2:
            return -1

        # Only let the owners of the bot use this command
        if source[0] in ircbot.owners and source[2] == ircbot.owner_host:
            self.whitelist.append(keywords[1])
            ircbot.fire(PRIVMSG(target, "Added '" + str(keywords[1] + "' to whitelist")))
        else:
            ircbot.fire(PRIVMSG(target, "Not authorised to use this command"))

    def usage(self):
        return "Usage: !whitelist <host>"

class Ban():
    def __init__(self):
        self.bans = []

    def execute(self, keywords, target, source, ircbot):
        if len(keywords) != 2:
            return -1

        # Only let the owners of the bot use this command
        if source[0] in ircbot.owners and source[2] == ircbot.owner_host:
            ircbot.commands['allow'].whitelist.remove(keywords[1])
            ircbot.fire(PRIVMSG(target, "Removed '" + str(keywords[1] + "' from whitelist")))
        else:
            ircbot.fire(PRIVMSG(target, "Not authorised to use this command"))

    def usage(self):
        return "Usage: !ban <host>"

class Part():
    def execute(self, keywords, target, source, ircbot):
        # Check a channel name was given and it starts with a #
        if len(keywords) != 2 or keywords[1][:1] != "#":
            return -1

        ircbot.fire(PART(keywords[1]))

    def usage(self):
        return "Usage: !part <channel name>"

class Join():
    def execute(self, keywords, target, source, ircbot):
        # Check a channel name was given and it starts with a #
        if len(keywords) != 2 or keywords[1][:1] != "#":
            return -1

        ircbot.fire(JOIN(keywords[1]))

    def usage(self):
        return "Usage: !join <channel name>"

class Commands():
    def execute(self, keywords, target, source, ircbot):
        ircbot.fire(PRIVMSG(target, ircbot.list_commands()))

    def usage(self):
        pass

"""
The actual bot
"""

class Bot(Component):
    def init(self, nick="Botivator", command_char="!",
             owners=["Motivator", "MotivatorAFK"], password_file="password.py",
             host_file="host", host="irc.snoonet.org", port="6667", channel="##arctantest"):

        self.host = host
        self.port = int(port)

        self.nick = nick
        self.password = open(password_file).read().strip()

        self.command_char = command_char

        self.owners = owners
        self.owner_host = open(host_file).read().strip()

        self.linkresolver = LinkResolver()

        self.commands = {
            #'command_name': [CommandClass, CanAnyoneUseIt?]
            'commands': [Commands(), True],
            'help': [Commands(), True],
            'join': [Join(), True],
            'part': [Part(), True],
            'ban': [Ban(), False],
            'allow': [Allow(), False],
            'source': [Source(), True],
            '4chan': [WatchFourChan(self), False],
            'hn': [WatchHackerNews(self), False],
            'reddit': [WatchReddit(self), False],
            '8ch': [WatchEightChan(self), False],
            'pastebin': [WatchPasteBin(self), False],
            'quote': [Quote(), True],
        }

        # Add owner to whitelist
        self.commands['allow'][0].whitelist.append(self.owner_host)

        TCPClient(channel=self.channel).register(self)
        IRC(channel=self.channel).register(self)

    def ready(self, component):
        """ Ready Event.

        Triggered by the underlying tcpclient Component when it is ready to
        start making a new connection.
        """

        self.fire(connect(self.host, self.port))

    def connected(self, host, port):
        """Connected Event.

        Triggered by the underlying tcpclient Component when a successfully
        connection has been made.
        """

        self.fire(NICK(self.nick))
        self.fire(USER(self.nick, self.nick, host, "Bot of Astonex or Softkitty"))

    def disconnected(self):
        """Disconnected Event.

        Triggered by the underlying tcpclient Component when the connection is lost
        """

        raise SystemExit(0)

    def numeric(self, source, numeric, *args):
        """Numeric Event.

        Triggered by the irc Protocol Component when we have received an irc
        Numberic Event from server we are connected to
        """

        # if nick is in use add an _ to the end of our name
        if numeric == ERR_NICKNAMEINUSE:
            self.fire(NICK("{0:s}_".format(args[0])))

        # else wait for end of motd to start sending commands
        elif numeric in (RPL_ENDOFMOTD, ERR_NOMOTD):
            self.fire(PRIVMSG("NICKSERV", "IDENTIFY " + self.password))

    def privmsg(self, source, target, message):
        """Message Event.

        Triggered by the irc Protocol Component for each message we receieve
        from the server
        """

        if message[:1] == self.command_char:
            self.parse(message, source, target)

        else:
            urls = findall("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", message)
            if urls:
                title = self.linkresolver.get_title(urls[0])
                self.fire(PRIVMSG(target, title))

    def parse(self, message, source, target):
        keywords = message.split(' ')
        key = keywords[0][1:]

        # Check it is a valid command
        if self.commands[key]:
            command = self.commands[key]
        else:
            return

        response = 0

        # Can anyone use it?
        if command[1]:
            response = command[0].execute(keywords, target, source, self)

        # Else check source is in whitelist
        elif source[2] in self.commands['allow'][0].whitelist:
            response = command[0].execute(keywords, target, source, self)

        if response == -1:
            self.fire(PRIVMSG(target, command[0].usage()))

    def list_commands(self):
        list = ""

        for key in self.commands:
            list += self.command_char + str(key) + " "

        return "Available commands: " + list

bot = Bot()
Debugger().register(bot)
bot.run()
