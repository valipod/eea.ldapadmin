from string import ascii_lowercase
import ldap, ldap.filter

user_attr_map = {
    'name': 'cn',
    'email': 'mail',
    'phone': 'telephoneNumber',
    'organisation': 'o',
    'address': 'postalAddress',
    'fax': 'facsimileTelephoneNumber',
    'url': 'labeledURI',
}

org_attr_map = {
    'name': 'o',
    'phone': 'telephoneNumber',
    'fax': 'facsimileTelephoneNumber',
    'url': 'labeledURI',
    'address': 'postalAddress',
    'street': 'street',
    'po_box': 'postOfficeBox',
    'postal_code': 'postalCode',
    'country': 'st',
    'locality': 'l',
}

class LdapAgent(object):
    def __init__(self, **config):
        self.conn = self.connect(config['ldap_server'])
        self._encoding = config.get('encoding', 'utf-8')
        self._user_dn_suffix = config.get('users_dn',
                                          "ou=Users,o=EIONET,l=Europe")
        self._org_dn_suffix = config.get('orgs_dn',
                                         "ou=Organisations,o=EIONET,l=Europe")
        self._role_dn_suffix = config.get('roles_dn',
                                          "ou=Roles,o=EIONET,l=Europe")
        self._bound = False

    def connect(self, server):
        conn = ldap.initialize('ldap://' + server)
        conn.protocol_version = ldap.VERSION3
        return conn

    def _role_dn(self, role_id):
        if role_id is None:
            id_bits = []
        else:
            id_bits = role_id.split('-')

        dn_start = ''
        for c in range(len(id_bits), 0, -1):
            dn_start += 'cn=%s,' % '-'.join(id_bits[:c])
        return dn_start + self._role_dn_suffix

    def _role_id(self, role_dn):
        if role_dn == self._role_dn_suffix:
            return None
        assert role_dn.endswith(',' + self._role_dn_suffix)
        role_dn_start = role_dn[ : - (len(self._role_dn_suffix) + 1)]
        dn_bits = role_dn_start.split(',')
        dn_bits.reverse()

        current_bit = None
        for bit in dn_bits:
            assert bit.startswith('cn=')
            bit = bit[len('cn='):]
            if current_bit is None:
                assert '-' not in bit
            else:
                assert bit.startswith(current_bit+'-')
                assert '-' not in bit[len(current_bit)+1:]
            current_bit = bit

        return current_bit

    def _user_dn(self, user_id):
        assert ',' not in user_id
        return 'uid=' + user_id + ',' + self._user_dn_suffix

    def _user_id(self, user_dn):
        assert user_dn.endswith(',' + self._user_dn_suffix)
        assert user_dn.startswith('uid=')
        user_id = user_dn[len('uid=') : - (len(self._user_dn_suffix) + 1)]
        assert ',' not in user_id
        return user_id

    def _org_dn(self, org_id):
        assert ',' not in org_id
        return 'cn=' + org_id + ',' + self._org_dn_suffix

    def _org_id(self, org_dn):
        assert org_dn.endswith(',' + self._org_dn_suffix)
        assert org_dn.startswith('cn=')
        org_id = org_dn[len('cn=') : - (len(self._org_dn_suffix) + 1)]
        assert ',' not in org_id
        return org_id

    def _unpack_user_info(self, dn, attr):
        out = {'dn': dn, 'id': self._user_id(dn)}
        for name, ldap_name in user_attr_map.iteritems():
            if ldap_name in attr:
                out[name] = attr[ldap_name][0].decode(self._encoding)
            else:
                out[name] = u""
        return out

    def _unpack_org_info(self, dn, attr):
        out = {'dn': dn, 'id': self._org_id(dn)}
        for name, ldap_name in org_attr_map.iteritems():
            if ldap_name in attr:
                out[name] = attr[ldap_name][0].decode(self._encoding)
            else:
                out[name] = u""
        return out

    def role_names_in_role(self, role_id):
        """
        Returns a mapping of `sub_role_id` to `description` for subroles
        of `role_id`.
        """

        query_dn = self._role_dn(role_id)
        result = self.conn.search_s(query_dn, ldap.SCOPE_ONELEVEL,
                        filterstr='(objectClass=groupOfUniqueNames)',
                        attrlist=('description',))

        out = {}
        for dn, attr in result:
            values = attr.get('description', [''])
            out[self._role_id(dn)] = values[0].decode(self._encoding)
        return out

    def filter_roles(self, pattern):
        query_dn = self._role_dn_suffix
        result = self.conn.search_s(query_dn, ldap.SCOPE_SUBTREE,
                        filterstr='(objectClass=groupOfUniqueNames)',
                        attrlist=())

        pattern_bits = pattern.split('-')

        out = set()
        for dn, attr in result:
            role_id = self._role_id(dn)
            if role_id is None:
                continue
            role_id_bits = role_id.split('-')
            if len(pattern_bits) > len(role_id_bits):
                continue
            for c in range(len(pattern_bits)):
                if pattern_bits[c] != '*':
                    if role_id_bits[c] != pattern_bits[c]:
                        break # not a march
            else:
                out.add(role_id) # because we found no mismatch
        return out

    def _query(self, dn):
        return self.conn.search_s(dn, ldap.SCOPE_BASE)[0][1]

    def members_in_role(self, role_id):
        """
        Returns a dictionary with 'user' and 'org' as keys, and lists of
        `user_id` or `org_id` as values - direct members of role `role_id`.
        """

        query_dn = self._role_dn(role_id)

        def member_tuples_from_result(result):
            out = set()
            for dn, attr in result:
                for member_dn in attr.get('uniqueMember', []):
                    if not member_dn:
                        # ignore blank member DNs
                        continue
                    if member_dn.endswith(self._org_dn_suffix):
                        out.add( ('orgs', self._org_id(member_dn)) )
                    elif member_dn.endswith(self._user_dn_suffix):
                        out.add( ('users', self._user_id(member_dn)) )
                    # else ignore the record
            return out

        # first, get all user ids in this role
        result = self.conn.search_s(query_dn, ldap.SCOPE_BASE,
                        filterstr='(objectClass=groupOfUniqueNames)',
                        attrlist=('uniqueMember',))
        all_members = member_tuples_from_result(result)

        # then get all user ids in sub-roles
        result = self.conn.search_s(query_dn, ldap.SCOPE_ONELEVEL,
                        filterstr='(objectClass=groupOfUniqueNames)',
                        attrlist=('uniqueMember',))
        members_in_sub_roles = member_tuples_from_result(result)

        # and return only users that are *not* in sub-roles
        out = {'users': [], 'orgs': []}
        for member_type, member_id in (all_members - members_in_sub_roles):
            out[member_type].append(member_id)
        return out

    def user_info(self, user_id):
        """
        Returns a dictionary of user information for user `user_id`.
        """

        query_dn = self._user_dn(user_id)
        result = self.conn.search_s(query_dn, ldap.SCOPE_BASE,
                        filterstr='(objectClass=organizationalPerson)')

        assert len(result) == 1
        dn, attr = result[0]
        assert dn == query_dn
        return self._unpack_user_info(dn, attr)

    def org_info(self, org_id):
        """
        Returns a dictionary of organisation information for `org_id`.
        """

        query_dn = self._org_dn(org_id)
        result = self.conn.search_s(query_dn, ldap.SCOPE_BASE)

        assert len(result) == 1
        dn, attr = result[0]
        assert dn == query_dn
        return self._unpack_org_info(dn, attr)

    def role_info(self, role_id):
        """
        Returns a dictionary describing the role `role_id`.
        """

        query_dn = self._role_dn(role_id)
        result = self.conn.search_s(query_dn, ldap.SCOPE_BASE)

        assert len(result) == 1
        dn, attr = result[0]
        assert dn == query_dn
        return {'description': attr.get('description', [""])[0]}

    def perform_bind(self, login_dn, login_pw):
        result = self.conn.simple_bind_s(login_dn, login_pw)
        # may throw ldap.INVALID_CREDENTIALS
        assert result == (ldap.RES_BIND, [])
        self._bound = True

    def _org_info_diff(self, org_id, old_info, new_info):
        def pack(value):
            return [value.encode(self._encoding)]

        for name in org_attr_map:
            old_value = old_info.get(name, u"")
            new_value = new_info.get(name, u"")
            ldap_name = org_attr_map[name]

            if old_value == new_value == '':
                pass

            elif old_value == '':
                yield (ldap.MOD_ADD, ldap_name, pack(new_value))

            elif new_value == '':
                yield (ldap.MOD_DELETE, ldap_name, pack(old_value))

            elif old_value != new_value:
                yield (ldap.MOD_REPLACE, ldap_name, pack(new_value))

    def create_org(self, org_id, org_info):
        """ Create a new organisation with attributes from `org_info` """
        assert self._bound, "call `perform_bind` before `create_org`"
        assert type(org_id) is str
        for ch in org_id:
            assert ch in ascii_lowercase + '_'
        attrs = [ (org_attr_map[name], [value.encode('utf-8')])
                  for name, value in sorted(org_info.iteritems()) ]
        result = self.conn.add_s(self._org_dn(org_id), attrs)
        assert result == (ldap.RES_ADD, [])

    def set_org_info(self, org_id, new_info):
        old_info = self.org_info(org_id)
        changes = tuple(self._org_info_diff(org_id, old_info, new_info))
        if not changes:
            return
        org_dn = self._org_dn(org_id)
        result = self.conn.modify_s(org_dn, changes)
        assert result == (ldap.RES_MODIFY, [])

    def delete_org(self, org_id):
        """ Remove the organisation `org_id` """
        assert self._bound, "call `perform_bind` before `delete_org`"
        result = self.conn.delete_s(self._org_dn(org_id))
        assert result == (ldap.RES_DELETE, [])

    def create_role(self, role_id, description):
        """
        Create the specified role.
        """

        assert self._bound, "call `perform_bind` before `create_role`"

        attrs = [
            ('objectClass', ['top', 'groupOfUniqueNames']),
            ('ou', [role_id.split('-')[-1]]),
            ('uniqueMember', ['']),
        ]
        if description:
            attrs.append( ('description', [description]) )

        role_dn = self._role_dn(role_id)

        try:
            result = self.conn.add_s(role_dn, attrs)
        except ldap.NO_SUCH_OBJECT:
            raise ValueError("Parent DN missing (trying to create %r)"
                             % role_dn)
        except ldap.ALREADY_EXISTS:
            raise ValueError("DN already exists (trying to create %r)"
                             % role_dn)

        assert result == (ldap.RES_ADD, [])

    def _sub_roles(self, role_id):
        role_dn = self._role_dn(role_id)
        result = self.conn.search_s(role_dn, ldap.SCOPE_SUBTREE,
                        filterstr='(objectClass=groupOfUniqueNames)',
                        attrlist=())

        sub_roles = []
        for dn, attr in result:
            sub_roles.append(dn)
        sub_roles.sort()
        sub_roles.reverse()

        return sub_roles

    def delete_role(self, role_id):
        assert self._bound, "call `perform_bind` before `delete_role`"
        for dn in self._sub_roles(role_id):
            result = self.conn.delete_s(dn)
            assert result == (ldap.RES_DELETE, [])

    def search_by_name(self, name):
        query_filter = ldap.filter.filter_format(
            '(&(objectClass=person)(|(uid=*%s*)(cn=*%s*)))', (name, name))

        result = self.conn.search_s(
            'ou=Users,o=EIONET,l=Europe', ldap.SCOPE_ONELEVEL,
            filterstr=query_filter)

        return [self._unpack_user_info(dn, attr) for (dn, attr) in result]

    def _member_dn(self, member_type, member_id):
        if member_type == 'user':
            return self._user_dn(member_id)
        elif member_type == 'org':
            return self._org_dn(member_id)
        else:
            raise ValueError('unknown member type %r' % member_type)

    def _add_member_dn_to_role_dn(self, role_dn, member_dn):
        result = self.conn.search_s(member_dn, ldap.SCOPE_BASE, attrlist=())
        if len(result) < 1:
            raise ValueError("DN not found: %r" % member_dn)

        result = self.conn.search_s(role_dn, ldap.SCOPE_BASE, attrlist=())
        if len(result) < 1:
            raise ValueError("DN not found: %r" % role_dn)

        while role_dn.endswith(self._role_dn_suffix): # including root
            try:
                result = self.conn.modify_s(role_dn, (
                    (ldap.MOD_ADD, 'uniqueMember', [member_dn]),
                ))
            # weird. sometimes one exception is thrown, sometimes the other:
            except (ldap.OBJECT_CLASS_VIOLATION, ldap.TYPE_OR_VALUE_EXISTS):
                return # already a member here; we can stop now.
            else:
                assert result == (ldap.RES_MODIFY, [])

            try:
                result = self.conn.modify_s(role_dn, (
                    (ldap.MOD_DELETE, 'uniqueMember', ['']),
                ))
            except ldap.NO_SUCH_ATTRIBUTE:
                pass # so the group was not empty. that's fine.
            else:
                assert result == (ldap.RES_MODIFY, [])

            role_dn = role_dn.split(',', 1)[1] # go up a level

    def add_to_role(self, role_id, member_type, member_id):
        assert self._bound, "call `perform_bind` before `add_to_role`"
        member_dn = self._member_dn(member_type, member_id)
        role_dn = self._role_dn(role_id)

        self._add_member_dn_to_role_dn(role_dn, member_dn)

    def _sub_roles_with_member(self, role_dn, member_dn):
        filter_tmpl = '(&(objectClass=groupOfUniqueNames)(uniqueMember=%s))'
        filterstr = ldap.filter.filter_format(filter_tmpl, (member_dn,))
        result = self.conn.search_s(role_dn, ldap.SCOPE_SUBTREE,
                                    filterstr=filterstr, attrlist=())
        for dn, attr in result:
            yield dn

    def _remove_member_dn_from_single_role_dn(self, role_dn, member_dn):
        # remove a single member from a single role

        # add '' to the memebrs list, in case we will remove the last one
        try:
            self.conn.modify_s(role_dn, (
                (ldap.MOD_ADD, 'uniqueMember', ['']),
            ))
        except ldap.OBJECT_CLASS_VIOLATION:
            pass # is someone else removing users at the same time?

        # actually remove the member
        try:
            try:
                self.conn.modify_s(role_dn, (
                    (ldap.MOD_DELETE, 'uniqueMember', [member_dn]),
                ))
            except ldap.NO_SUCH_ATTRIBUTE:
                pass # role was removed by someone else?!

        finally:
            # attempt to remove '', in case other members still exist
            try:
                # removing '' will fail if it's the last member (which is
                # just fine).
                self.conn.modify_s(role_dn, (
                    (ldap.MOD_DELETE, 'uniqueMember', ['']),
                ))
            except ldap.OBJECT_CLASS_VIOLATION:
                pass # so we removed the last member, '' must remain

    def _remove_member_dn_from_role_dn(self, role_dn, member_dn):
        result = self.conn.search_s(member_dn, ldap.SCOPE_BASE, attrlist=())
        if len(result) < 1:
            raise ValueError("DN not found: %r" % member_dn)

        result = self.conn.search_s(role_dn, ldap.SCOPE_BASE, attrlist=())
        if len(result) < 1:
            raise ValueError("DN not found: %r" % role_dn)

        roles = list(self._sub_roles_with_member(role_dn, member_dn))
        if not roles:
            raise ValueError("DN %r is not a member of %r" %
                             (member_dn, role_dn))
        roles.sort()
        roles.reverse()
        for sub_role_dn in roles:
            self._remove_member_dn_from_single_role_dn(member_dn, sub_role_dn)

    def remove_from_role(self, role_id, member_type, member_id):
        """
        Remove a role member. We must remove the member from any sub-roles too.

        Since we use the `groupOfUniqueNames` and `uniqueMember` classes, we
        need to do some juggling with a blank placeholder member:
          * step 1: try to add '' as member, so the role is never empty
          * step 2: remove our member as requested
          * step 3: try to remove member '' (added above). this will only
            succeed if the role is not empty.
        """
        assert self._bound, "call `perform_bind` before `remove_from_role`"

        member_dn = self._member_dn(member_type, member_id)
        role_dn = self._role_dn(role_id)

        self._remove_member_dn_from_single_role_dn(role_dn, member_dn)

    def list_member_roles(self, member_type, member_id):
        """
        List the role IDs where this user/organisation is a member.
        """

        member_dn = self._member_dn(member_type, member_id)
        return [self._role_id(role_dn) for role_dn in
                self._sub_roles_with_member(self._role_dn(None), member_dn)]
