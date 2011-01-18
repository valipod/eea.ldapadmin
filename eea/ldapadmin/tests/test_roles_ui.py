import unittest
from mock import Mock
from eea.ldapadmin.roles_editor import RolesEditor

def parse_html(html):
    from lxml.html.soupparser import fromstring
    return fromstring(html)

class StubbedRolesEditor(RolesEditor):
    def _zope2_wrapper(self, body_html):
        return "<html>%s</html>" % body_html

    def absolute_url(self):
        return "URL"

def mock_request():
    request = Mock()
    request.SESSION = {}
    return request

user_info_fixture = {
    'id': "jsmith",
    'name': "Joe Smith",
    'email': u"jsmith@example.com",
    'phone': u"555 1234",
    'fax': u"555 6789",
    'organisation': "My company",
}


class BrowseTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor({})
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        self.request.form = {'role_id': 'places'}
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        self.mock_agent.members_in_role.return_value = {'users':[], 'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }

    def test_browse_subroles(self):
        role_names = {'bank': "Bank for Test", 'agency': "The Agency"}
        self.mock_agent.role_names_in_role.return_value = role_names

        page = parse_html(self.ui.index_html(self.request))

        self.mock_agent.role_names_in_role.assert_called_once_with('places')
        roles_ul = page.xpath('ul[@class="sub-roles"]')[0]
        self.assertEqual(len(roles_ul.xpath('li')), 2)
        self.assertEqual(roles_ul.xpath('li/a')[0].text, "agency")
        self.assertEqual(roles_ul.xpath('li/span')[0].text, "The Agency")
        self.assertEqual(roles_ul.xpath('li/a')[1].text, "bank")
        self.assertEqual(roles_ul.xpath('li/span')[1].text, "Bank for Test")

    def test_browse_role_info(self):
        page = parse_html(self.ui.index_html(self.request))

        self.assertEqual(page.xpath('//h1')[0].text, "Various places")
        self.mock_agent.role_info.assert_called_once_with('places')

    def test_members_info(self):
        self.mock_agent.members_in_role.return_value = {
            'users': ['jsmith'], 'orgs': [],
        }
        self.mock_agent.user_info.return_value = dict(user_info_fixture)

        page = parse_html(self.ui.index_html(self.request))

        self.mock_agent.members_in_role.assert_called_once_with('places')
        self.mock_agent.user_info.assert_called_once_with('jsmith')

        txt = lambda xp, ctx=page: ctx.xpath(xp)[0].text_content().strip()
        user_li = page.xpath('//ul[@class="role-members"]/li')[0]
        self.assertEqual(txt('tt[@class="user-id"]', user_li), 'jsmith')
        self.assertEqual(txt('span[@class="user-name"]', user_li),
                         user_info_fixture['name'])
        self.assertEqual(txt('a[@class="user-email"]', user_li),
                         user_info_fixture['email'])
        self.assertEqual(txt('span[@class="user-phone"]', user_li),
                         user_info_fixture['phone'])
        self.assertEqual(txt('span[@class="user-organisation"]', user_li),
                         user_info_fixture['organisation'])
