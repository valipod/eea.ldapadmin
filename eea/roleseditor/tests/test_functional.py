import unittest
import fixtures

class SeleniumWrapper(object):
    def start_up_selenium(self):
        from selenium import selenium as selenium_client
        import socket

        self.config = {
            'test_site_url': 'http://localhost:8080/',
            'selenium_grid_port': '5555',
            'browser': '*firefox',
        }
        try:
            import testconfig
        except ImportError:
            pass
        else:
            config_from_file = testconfig.config[
                'eea.roleseditor.tests.functional'] or {}
            self.config.update(config_from_file)

        self.selenium = selenium_client('localhost',
                                        self.config['selenium_grid_port'],
                                        self.config['browser'],
                                        self.config['test_site_url'])

        try:
            self.selenium.start()
        except socket.error, e:
            assert False, "Could not connect to selenium: %s" % e

    def shut_down_selenium(self):
        self.selenium.stop()

def login(S):
    S.open('/login')
    S.type('__ac_name', "admin")
    S.type('__ac_password', "admin")
    S.click('//input[@value=" Login "]')
    S.wait_for_page_to_load(1000)

def logout(S):
    S.open('/login/logout')

def create_roles_editor(S):
    login(S)
    S.open('/manage_addProduct'
                  '/EionetRolesEditor/manage_add_editor_html')
    S.type('id', 'roles')
    S.type('login_dn', 'uid=_admin,ou=Users,o=EIONET,l=Europe')
    S.type('login_pw', 'admin-test-pw')
    S.type('users_dn', 'ou=Users,o=EIONET,l=Europe')
    S.type('orgs_dn', 'ou=Organisations,o=EIONET,l=Europe')
    S.type('roles_dn', 'ou=Roles,o=EIONET,l=Europe')
    S.click('//input[@type="submit"]')
    S.wait_for_page_to_load(1000)
    logout(S)

def remove_roles_editor(S):
    login(S)
    S.open('/manage_workspace')
    S.wait_for_page_to_load(1000)
    S.click('//input[@name="ids:list"][@value="roles"]')
    S.click('//input[@type="submit"][@name="manage_delObjects:method"]')
    S.wait_for_page_to_load(1000)
    logout(S)

def setUpModule():
    global _selenium_wrapper
    _selenium_wrapper = SeleniumWrapper()
    _selenium_wrapper.start_up_selenium()
    create_roles_editor(_selenium_wrapper.selenium)

def tearDownModule():
    remove_roles_editor(_selenium_wrapper.selenium)
    _selenium_wrapper.shut_down_selenium()

def send_ldap_fixture(ldap_fixture, config):
    from urllib import urlencode
    from urllib2 import urlopen, Request
    import simplejson as json
    data = urlencode({'data_json': json.dumps(ldap_fixture)})
    fixture_rq = Request(config['test_site_url'] + 'mock_ldap_load', data)
    assert urlopen(fixture_rq).read() == 'LDAP mock data loaded'

class FunctionalTest(unittest.TestCase):
    def setUp(self):
        self.selenium = _selenium_wrapper.selenium
        self.config = _selenium_wrapper.config

    def test_browse(self):
        S = self.selenium
        is_elem = S.is_element_present
        txt = S.get_text

        send_ldap_fixture(fixtures.ldap_data, self.config)

        loc_role_id = '//h1/tt'
        loc_parent_link = '//p[contains(text(), "up:")]'

        S.open('/roles')
        assert not is_elem(loc_role_id)
        assert not is_elem(loc_parent_link)
        assert is_elem('//a[text()="A"]')

        S.click('//a[text()="A"]')
        S.wait_for_page_to_load(2000)
        assert S.get_location().endswith("?role_id=A")
        assert is_elem(loc_role_id)
        assert txt(loc_role_id) == 'A'
        assert is_elem(loc_parent_link)
        assert txt(loc_parent_link + '/a') == '[root]'
        assert is_elem('//a[text()="A-B"]')
        assert txt('//li[a[text()="A-B"]]').endswith("Role [A B]")

        S.click('//a[text()="A-C"]')
        S.wait_for_page_to_load(2000)
        assert S.get_location().endswith("?role_id=A-C")
        assert is_elem(loc_role_id)
        assert txt(loc_role_id) == 'A-C'
        assert is_elem(loc_parent_link)
        assert txt(loc_parent_link + '/a') == 'A'

    def test_user_info(self):
        S = self.selenium
        is_elem = S.is_element_present
        txt = S.get_text

        send_ldap_fixture(fixtures.ldap_data, self.config)

        loc_user_li = "css=ul.role-members li"

        login(S)
        S.open('/roles?role_id=A')
        assert is_elem(loc_user_li + " tt.user-id:contains(userone)")
        assert not is_elem(loc_user_li + " tt.user-id:contains(usertwo)")
        assert not is_elem(loc_user_li + " tt.user-id:contains(userthree)")
        logout(S)

        # TODO: make sure anonymous users don't see full user info

    def test_filter_roles(self):
        S = self.selenium
        is_elem = S.is_element_present
        txt = S.get_text

        send_ldap_fixture(fixtures.ldap_data, self.config)

        loc_search_input = '//form[@name="filter"]/input[@type="search"]'

        S.open('/roles/filter')
        assert is_elem(loc_search_input)

        S.type(loc_search_input, "K-*-O")
        S.click('//form[@name="filter"]/input[@type="submit"]')
        S.wait_for_page_to_load(2000)

        assert txt('//h3/tt') == "K-M-O"
        assert (txt('//ul[@class="role-members"]/li/span[@class="user-name"]')
                == "User Four")
