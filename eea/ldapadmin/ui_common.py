from Acquisition import Implicit
from zope.pagetemplate.pagetemplatefile import PageTemplateFile as Z3Template
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from Products.PageTemplates.PageTemplateFile import PageTemplateFile\
                                                 as Z2Template

def load_template(name, _memo={}):
    if name not in _memo:
        _memo[name] = Z3Template(name, globals())
    return _memo[name]

class SessionMessages(object):
    def __init__(self, request, name):
        self.request = request
        self.name = name

    def add(self, msg_type, msg):
        session = self.request.SESSION
        if self.name not in session.keys():
            session[self.name] = PersistentMapping()
        messages = session[self.name]
        if msg_type not in messages:
            messages[msg_type] = PersistentList()
        messages[msg_type].append(msg)

    def html(self):
        session = self.request.SESSION
        if self.name in session.keys():
            messages = dict(session[self.name])
            del session[self.name]
        else:
            messages = {}
        tmpl = load_template('zpt/session_messages.zpt')
        return tmpl(messages=messages)

zope2_wrapper = Z2Template('zpt/zope2_wrapper.zpt', globals())
class Zope3TemplateInZope2(Implicit):
    def __call__(self, name, **options):
        tmpl = load_template(name)
        zope2_tmpl = zope2_wrapper.__of__(self.aq_parent)
        return zope2_tmpl(body_html=tmpl(**options))
