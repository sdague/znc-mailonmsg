#  Copyright 2013 Sean Dague <sean@dague.net>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import pprint
import sys
import traceback

# Import the email modules we'll need
from email import header
from email.mime import text
import smtplib
import znc


pp = pprint.PrettyPrinter()


def _is_self(*args):
    """Utility method to make sure only calling on right modules."""
    if len(args) > 1 and type(args[0]) == mailonmsg:
        return args[0]
    return None


def trace(fn):
    """Useful decorator for debugging."""
    def wrapper(*args, **kwargs):
        s = _is_self(*args)
        if s:
            s.PutModule("TRACE: %s" % (fn.__name__))
        fn(*args, **kwargs)
    return wrapper


def catchfail(fn):
    """Catch exceptions and get them onto the module channel."""
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            s = _is_self(*args)
            if s:
                s.PutModule("Failed with %s" % (e))
                # then get the whole stack trace out
                lines = traceback.format_exception(exc_type, exc_value,
                                                   exc_traceback)
                for line in lines:
                    s.PutModule(line)
    return wrapper


class mailonmsg(znc.Module):
    """Module to email messages to users when they are away.

    After moving from maiu to znc, the one feature I missed was the
    email when away. This tries to replicate this feature through emailing
    highlights as well as privmsg to a predefined email account.
    """
    description = 'send email on message'

    keywords = []
    pending = {}

    def _should_send(self, nick, msg):
        """Conditions on which we should send a notification."""
        if not self.GetNetwork().IsIRCAway():
            self.PutModule("Not sending because not away")
            return False
        else:
            self.PutModule("Sending email")
            return True

    def _highlight(self, msg):
        if msg.find(self.GetNetwork().GetCurNick()) != -1:
            return True

        for word in self.keywords:
            if msg.find(word) != -1:
                return True

        return False

    @catchfail
    def send_email(self, nick, msg):
        if not self._should_send(nick, msg):
            return False

        email = text.MIMEText(msg.encode('utf-8'), 'plain', 'utf-8')

        email['Subject'] = header.Header('IRC message from %s' % nick, 'utf-8')
        email['From'] = self.nv['from']
        email['To'] = self.nv['to']
        s = smtplib.SMTP('localhost')
        s.sendmail(email['From'], [email['To']], email.as_string())
        s.quit()

    @catchfail
    @trace
    def OnStatusCommand(self, cmd):
        print("STATUS: %s" % cmd)
        return znc.CONTINUE

    def OnLoad(self, args, msg):
        self.keywords = [
            self.GetUser().GetNick()
            ]

        arglist = args.split()
        for arg in arglist:
            k, v = arg.split("=")
            self.nv[k] = v
        self.PutModule("LOADED with ARGS: %s" % args)
        # TODO(sdague): in future take in args for additional keywords
        #print("ARGS: %s" % args)
        #print("MSG: %s" % msg)
        return znc.CONTINUE

    @catchfail
    def OnPrivMsg(self, nick, msg):
        # self.PutModule("PRIVMSG received from %s" % nick.GetNick())
        self.send_email(nick.GetNick(), msg.s)
        return znc.CONTINUE

    @catchfail
    def OnChanMsg(self, nick, channel, msg):
        if self._highlight(msg.s):
            self.send_email(nick.GetNick(),
                            "%s: %s" % (channel.GetName(), msg.s))
        return znc.CONTINUE
