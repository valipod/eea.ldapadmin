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
class TemplateRenderer(Implicit):
    def __init__(self, common_factory=lambda ctx: {}):
        self.common_factory = common_factory

    def render(self, name, **options):
        context = self.aq_parent
        template = load_template(name)
        namespace = template.pt_getContext((), options)
        namespace['common'] = self.common_factory(context)
        return template.pt_render(namespace)

    def wrap(self, body_html):
        context = self.aq_parent
        zope2_tmpl = zope2_wrapper.__of__(context)
        return zope2_tmpl(body_html=body_html)

    def __call__(self, name, **options):
        return self.wrap(self.render(name, **options))
