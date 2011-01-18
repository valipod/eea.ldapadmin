import unittest
from mock import Mock
from eea.ldapadmin.roles_editor import RolesEditor

def plaintext(element):
    import re
    return re.sub(r'\s\s+', ' ', element.text_content()).strip()

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

def session_messages(request):
    return request.SESSION.get('eea.ldapadmin.roles_editor.messages')


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

class CreateDeleteRolesTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor({})
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']
        def agent_role_id(role_dn):
            assert role_dn.startswith('test-dn:')
            return role_dn[len('test-dn:'):]
        self.mock_agent._role_id = agent_role_id

    def test_link_from_browse(self):
        self.mock_agent.members_in_role.return_value = {'users':[], 'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.index_html(self.request))

        create_url = "URL/create_role_html?parent_role_id=places"
        create_links = page.xpath('//a[@href="%s"]' % create_url)
        self.assertEqual(len(create_links), 1)
        self.assertEqual(create_links[0].text, "Create sub-role")

        delete_url = "URL/delete_role_html?role_id=places"
        delete_links = page.xpath('//a[@href="%s"]' % delete_url)
        self.assertEqual(len(delete_links), 1)
        self.assertEqual(delete_links[0].text_content(), "Delete role places")

    def test_create_role_html(self):
        self.request.form = {'parent_role_id': 'places'}

        page = parse_html(self.ui.create_role_html(self.request))

        self.assertEqual(plaintext(page.xpath('//h1')[0]),
                         "Create role under places")
        self.assertEqual(page.xpath('//form')[0].attrib['action'],
                         "URL/create_role")
        input_parent = page.xpath('//form//input[@name="parent_role_id"]')[0]
        self.assertEqual(input_parent.attrib['value'], 'places')
        input_desc_xpath = '//form//input[@name="description:utf8:ustring"]'
        self.assertEqual(len(page.xpath(input_desc_xpath)), 1)

    def test_create_role_submit(self):
        self.request.form = {'parent_role_id': 'places',
                             'role_id_frag': 'shiny',
                             'description': "Shiny new role"}

        self.ui.create_role(self.request)

        self.mock_agent.create_role.assert_called_once_with(
            'places-shiny', "Shiny new role")
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places-shiny')

        msg = "Created role places-shiny 'Shiny new role'"
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_create_role_submit_unicode(self):
        self.request.form = {'parent_role_id': 'places',
                             'role_id_frag': 'shiny',
                             'description': "Shiny new role"}
        self.ui.create_role(self.request)
        self.mock_agent.create_role.assert_called_once_with(
            'places-shiny', "Shiny new role")

    # TODO test add with bad role_id_frag

    def test_delete_role_html(self):
        self.request.form = {'role_id': 'places-bank'}
        self.mock_agent._sub_roles.return_value = [
            'test-dn:places-bank',
            'test-dn:places-bank-central',
            'test-dn:places-bank-branch',
        ]

        page = parse_html(self.ui.delete_role_html(self.request))

        self.mock_agent._sub_roles.assert_called_once_with('places-bank')
        self.assertEqual([plaintext(li) for li in page.xpath('//form/ul/li')],
                         ['places-bank',
                          'places-bank-central',
                          'places-bank-branch'])

    def test_delete_role(self):
        self.request.form = {'role_id': 'places-bank'}

        self.ui.delete_role(self.request)

        self.mock_agent.delete_role.assert_called_once_with('places-bank')
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
