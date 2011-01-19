import unittest
from copy import deepcopy
from mock import Mock
from eea.ldapadmin.roles_editor import RolesEditor
from eea.ldapadmin.ui_common import load_template

def plaintext(element):
    import re
    return re.sub(r'\s\s+', ' ', element.text_content()).strip()

def parse_html(html):
    from lxml.html.soupparser import fromstring
    return fromstring(html)

class StubbedRolesEditor(RolesEditor):
    def _render_template(self, name, **options):
        return "<html>%s</html>" % load_template(name)(**options)

    def absolute_url(self):
        return "URL"

def mock_request():
    request = Mock()
    request.SESSION = {}
    return request

user_map_fixture = {
    'jsmith': {
        'id': "jsmith",
        'name': "Joe Smith",
        'email': u"jsmith@example.com",
        'phone': u"555 1234",
        'fax': u"555 6789",
        'organisation': "My company",
    },
    'anne': {
        'id': "anne",
        'name': "Anne Tester",
        'email': u"anne@example.com",
        'phone': u"555 32879",
        'fax': u"",
        'organisation': "Some Agency",
    },
}

user_info_fixture = user_map_fixture['jsmith']

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
        self.request.form = {'parent_role_id': 'places', 'slug': 'shiny',
                             'description': "Shiny new role"}

        self.ui.create_role(self.request)

        self.mock_agent.create_role.assert_called_once_with(
            'places-shiny', "Shiny new role")
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places-shiny')

        msg = "Created role places-shiny 'Shiny new role'"
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_create_role_submit_unicode(self):
        self.request.form = {'parent_role_id': 'places', 'slug': 'shiny',
                             'description': u"Shiny new r\u014dle"}
        self.ui.create_role(self.request)
        self.mock_agent.create_role.assert_called_once_with(
            'places-shiny', u"Shiny new r\u014dle")

    def test_create_role_submit_invalid(self):
        self.request.form = {'parent_role_id': 'places', 'slug': 'SHINY',
                             'description': "Shiny new role"}
        self.ui.create_role(self.request)
        self.assertEqual(self.mock_agent.create_role.call_count, 0)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/create_role_html?parent_role_id=places')

        msg = ("Invalid role name, it must contain only lowercase "
               "latin letters.")
        self.assertEqual(session_messages(self.request), {'error': [msg]})

        self.request.form = {'parent_role_id': 'places'}
        #print self.ui.create_role_html(self.request)
        page = parse_html(self.ui.create_role_html(self.request))

        role_id_xp = '//form//input[@name="slug:utf8:ustring"]'
        role_desc_xp = '//form//input[@name="description:utf8:ustring"]'
        self.assertEqual(page.xpath(role_id_xp)[0].attrib['value'], 'SHINY')
        self.assertEqual(page.xpath(role_desc_xp)[0].attrib['value'],
                         "Shiny new role")

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

class AddRemoveRoleMembersTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor({})
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']

    def test_links(self):
        self.mock_agent.members_in_role.return_value = {'users':[], 'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.index_html(self.request))

        add_url = "URL/add_to_role_html?role_id=places"
        add_links = page.xpath('//a[@href="%s"]' % add_url)
        self.assertEqual(len(add_links), 1)
        self.assertEqual(add_links[0].text, "Add new members")

    def test_add_user_html(self):
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.add_to_role_html(self.request))

        self.assertEqual(self.mock_agent.search_by_name.call_count, 0)
        self.assertEqual(plaintext(page.xpath('//h1')[0]),
                         "Add users to role places")

    def test_add_user_search_html(self):
        self.request.form = {'role_id': 'places', 'name': 'smith'}
        self.mock_agent.search_by_name.return_value = [user_info_fixture]

        page = parse_html(self.ui.add_to_role_html(self.request))

        self.mock_agent.search_by_name.assert_called_once_with('smith')
        name = plaintext(page.xpath('//ul/li/span[@class="user-name"]')[0])
        self.assertEqual(name, "Joe Smith")
        form = page.xpath('//form[@name="add-user"]')[0]
        self.assertEqual(form.attrib['action'], 'URL/add_to_role')

    def test_add_user_search_html_no_results(self):
        self.request.form = {'role_id': 'places', 'name': 'smith'}
        self.mock_agent.search_by_name.return_value = []

        page = parse_html(self.ui.add_to_role_html(self.request))

        self.assertEqual(plaintext(page.xpath('//p[@class="no-results"]')[0]),
                         "Found no users matching smith.")

    def test_add_user_submit(self):
        self.request.form = {'role_id': 'places', 'user_id': 'jsmith'}

        self.ui.add_to_role(self.request)

        self.mock_agent.add_to_role.assert_called_once_with(
            'places', 'user', 'jsmith')
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        msg = "User 'jsmith' added to role 'places'"
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_remove_user_html(self):
        self.mock_agent.members_in_role.return_value = {'users':['jsmith'],
                                                        'orgs':[]}
        self.mock_agent.role_names_in_role.return_value = {}
        self.mock_agent.role_info.return_value = {
            'description': "Various places",
        }
        self.mock_agent.user_info.return_value = dict(user_info_fixture,
                                                      id='jsmith')
        self.request.form = {'role_id': 'places'}

        page = parse_html(self.ui.index_html(self.request))

        remove_form = page.xpath('//form[@name="remove-users"]')[0]
        user_li = remove_form.xpath('.//ul[@class="role-members"]/li')[0]
        user_checkbox = user_li.xpath('input[@name="user_id_list:list"]')[0]
        self.assertEqual(user_checkbox.attrib['value'], 'jsmith')

    def test_remove_user_submit(self):
        self.request.form = {'role_id': 'places', 'user_id_list': ['jsmith']}

        self.ui.remove_from_role(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        msg = "Users ['jsmith'] removed from role 'places'"
        self.assertEqual(session_messages(self.request), {'info': [msg]})

    def test_remove_user_submit_nothing(self):
        self.request.form = {'role_id': 'places'}

        self.ui.remove_from_role(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/?role_id=places')
        self.assertEqual(session_messages(self.request), None)


class UserSearchTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor({})
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']

    def test_plain(self):
        self.request.form = {}
        page = parse_html(self.ui.search_users(self.request))

        form = page.xpath('//form[@name="search-users"]')[0]
        self.assertEqual(len(form.xpath('.//input[@name="name"]')), 1)

    def test_results(self):
        self.request.form = {'name': 'smith'}
        self.mock_agent.search_by_name.return_value = [user_info_fixture]

        page = parse_html(self.ui.search_users(self.request))

        self.mock_agent.search_by_name.assert_called_once_with('smith')
        name = plaintext(page.xpath('//ul/li/span[@class="user-name"]')[0])
        self.assertEqual(name, "Joe Smith")

    def test_no_result(self):
        self.request.form = {'name': 'smith'}
        self.mock_agent.search_by_name.return_value = []

        page = parse_html(self.ui.search_users(self.request))

        self.assertEqual(plaintext(page.xpath('//p[@class="no-results"]')[0]),
                         "Found no users matching smith.")

    def test_user_roles_html(self):
        self.request.form = {'user_id': 'jsmith'}
        self.mock_agent.list_member_roles.return_value = ['places-bank',
                                                          'places-bank-branch']

        page = parse_html(self.ui.search_users(self.request))

        roles_div = page.xpath('//div[@class="user-roles"]')[0]
        self.assertEqual(plaintext(roles_div.xpath('h2')[0]),
                         "User jsmith is a member of:")
        self.mock_agent.list_member_roles.assert_called_once_with(
            'user', 'jsmith')
        self.assertEqual([plaintext(li) for li in roles_div.xpath('ul/li')],
                         ['places-bank', 'places-bank-branch'])

    def _mock_for_user_roles(self):
        self.mock_agent._sub_roles.return_value = [
            'test-dn:places-bank',
            'test-dn:places-bank-central',
            'test-dn:places-bank-branch',
        ]
        self.mock_agent.list_member_roles.return_value = [
            'places', 'places-bank', 'places-bank-central']
        def agent_role_id(role_dn):
            assert role_dn.startswith('test-dn:')
            return role_dn[len('test-dn:'):]
        self.mock_agent._role_id = agent_role_id

    def test_user_remove_from_role_html(self):
        self.request.form = {'role_id': 'places', 'user_id': 'jsmith'}
        self._mock_for_user_roles()

        page = parse_html(self.ui.remove_user_from_role_html(self.request))

        self.assertEqual(plaintext(page.xpath('//h1')[0]), "Revoke membership")
        self.assertEqual(page.xpath('//form')[0].attrib['action'],
                         'URL/remove_user_from_role')
        self.assertEqual(plaintext(page.xpath('//form//p')[0]),
                         "Remove jsmith from the following roles:")
        self.assertEqual([plaintext(li) for li in page.xpath('//form/ul/li')],
                         ['places-bank', 'places-bank-central'])

    def test_user_remove_from_role_submit(self):
        self.request.form = {'role_id': 'places', 'user_id': 'jsmith'}
        self._mock_for_user_roles()

        self.ui.remove_user_from_role(self.request)

        self.mock_agent.remove_from_role.assert_called_once_with(
            'places', 'user', 'jsmith')
        self.request.RESPONSE.redirect.assert_called_with(
             'URL/search_users?user_id=jsmith')
        msg = ("User 'jsmith' removed from roles "
               "'places-bank', 'places-bank-central'.")
        self.assertEqual(session_messages(self.request), {'info': [msg]})

class FilterTest(unittest.TestCase):
    def setUp(self):
        self.ui = StubbedRolesEditor({})
        self.mock_agent = Mock()
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        self.request = mock_request()
        user = self.request.AUTHENTICATED_USER
        user.getRoles.return_value = ['Authenticated']

        org_membership = {
            'places-bank': {'users': sorted(user_map_fixture.keys()),
                            'orgs': []},
            'places-shiny': {'users': [], 'orgs': []},
        }
        self.mock_agent.filter_roles.return_value = org_membership.keys()
        self.mock_agent.members_in_role.side_effect = org_membership.get
        self.mock_agent.user_info.side_effect = deepcopy(user_map_fixture).get

    def check_query_results(self, page):
        role_ids = [tt.text for tt in page.xpath('//h3/tt')]
        self.assertEqual(role_ids, ['places-bank'])
        # TODO we should also list places-shiny somehow
        user_ids = [tt.text for tt in page.xpath('//tt[@class="user-id"]')]
        self.assertEqual(user_ids, ['anne', 'jsmith'])

    def test_filter_html(self):
        self.request.form = {'pattern': 'places-*'}

        page = parse_html(self.ui.filter(self.request))

        pattern_input = page.xpath('//form/input[@type="search"]')[0]
        self.assertEqual(pattern_input.attrib['value'], 'places-*')
        self.check_query_results(page)

    def test_saved_query_html(self):
        from eea.ldapadmin.query import Query
        query_ob = Query()
        query_ob.pattern = 'places-*'
        query_ob._get_ldap_agent = lambda: self.mock_agent
        query_ob._render_template = self.ui._render_template

        page = parse_html(query_ob.index_html(self.request))

        self.check_query_results(page)

    def test_no_results(self):
        self.request.form = {'pattern': 'places-*'}
        self.mock_agent.filter_roles.return_value = []

        page = parse_html(self.ui.filter(self.request))

        self.assertEqual(plaintext(page.xpath('//p[@class="no-results"]')[0]),
                         "No roles found matching places-*.")
