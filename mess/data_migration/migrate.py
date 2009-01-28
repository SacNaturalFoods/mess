#!/usr/bin/python

# This script is intended to populate the MESS Database for the first time.
# 
# Currently this script only imports members in Section 1.0 (active) and 
# Section 4.0 (multi-member information).  All other sections are SKIPPED.
#
# Beware: Some accounts get imported incorrectly, and must be fixed
# by hand after importing.
#
# You probably want to remove all fixtures before you run this...

import sys
from os.path import dirname, abspath
sys.path.append(dirname(dirname(abspath(__file__))))
import settings
from django.core.management import setup_environ
setup_environ(settings)

# these imports raise errors if placed before setup_environ(settings)
import string
import time
import re
import xlrd
from random import choice
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db import transaction

from membership import models

MAXLINES = 20000    # only import first N members for debugging

def prepare_columns(headers):
    '''
    define where to get each data chunk and how to handle it
    '''
    return {
        'account_name': Column(headers, source=0, parser=strip_notes),
        'section': Column(headers, 'Section'),
        'active_members': Column(headers, 'Active Members', parser=int_or_one),
        'has_proxy': Column(headers, 'Proxy Shopper', parser=is_nonspace),
        'account': [
            Column(headers, source=0, parser=strip_notes)],
        'member': [
            Column(headers, 'Primary Member', make_username),
            Column(headers, 'Primary Member', get_first_name, 'user.first_name'),
            Column(headers, 'Primary Member', get_last_name, 'user.last_name'),
            Column(headers, source=generate_pass, dest='user.password'),
            Column(headers, 'Join Date', date_format, 'date_joined'),
            Column(headers, 'Has key?', is_yes, 'has_key'),
            Column(headers, 'phone #', porter=create_phone),
            Column(headers, 'second phone #', porter=create_phone),
            Column(headers, 'email', porter=create_email),
            Column(headers, 'Street Address & Apt / City State / ZIP',
                porter=split_and_create_address) ],
        'proxy': [
            Column(headers, 'Proxy Shopper', make_username),
            Column(headers, 'Proxy Shopper', get_first_name, 'user.first_name'),
            Column(headers, 'Proxy Shopper', get_last_name, 'user.last_name'),
            Column(headers, source=generate_pass, dest='user.password'),
            Column(headers, 'Proxy Shopper #', porter=create_phone)] }


class Cell:
    ''' 
    roughly, each excel cell gets one of these
    specifically, each row has one of these for each Column, as per below
    so the 100,000 cell objects will each point to one of 100 column objects
    '''
    def __init__(self, excel_row, column, backup_row=None):
        self.column = column
        self.data = column.fetch_data(excel_row, backup_row=backup_row)

    def migrate(self, new_object):
        self.column.migrate(self.data, new_object)

class Column:
    ''' 
    roughly, each excel column gets one of these,
    in which case 'source' is normally the header like 'Join Date'

    however, a Column object can grab data from various excel columns by
    specifying a 'source' function.  For example, 'notes' could be a Column
    that finds 'notes' data scattered across each row.
    '''
    def __init__(self, headers, source, parser=None, dest=None, porter=None):
        self.parser = parser
        self.dest = dest
        if isinstance(source, basestring):
            try:
                self.source_col = headers.index(source)
            except ValueError:
                print 'ERROR: Cannot find excel column "%s".' % source
                raise
        elif callable(source):
            self.fetch_data = source
        else:
            self.source_col = int(source)
        if porter:
            self.migrate = porter

    def fetch_data(self, excel_row, backup_row=None):
        val = unicode(excel_row[self.source_col].value).strip()
        if (val == '' or val.isspace()) and backup_row:
            val = unicode(backup_row[self.source_col].value).strip()
        if self.parser:
            return self.parser(val)
        else:
            return val

    def migrate(self, data, new_object):
        if self.dest == None:
            # should perhaps annotate that we're throwing data away...
            pass
        elif self.dest[:5] == 'user.':
            setattr(new_object.user, self.dest[5:], data)
        else:
            setattr(new_object, self.dest, data)


class PortAccount:
    def __init__(self, excel_row, columns):
        self.sec1_row = excel_row
        self.has_removed_sec1_members = False
        self.cells = [Cell(excel_row, column) for column in columns['account']]
        self.members = [
                    [Cell(excel_row, column) for column in columns['member']] ]
        if columns['has_proxy'].fetch_data(excel_row):
            self.members.append(
                    [Cell(excel_row, column) for column in columns['proxy']] )

    def add_sec4_row(self, excel_row, columns):
        if not self.has_removed_sec1_members:
            self.members = []
            self.has_removed_sec1_members = True
        self.members.append( 
                    [Cell(excel_row, column, backup_row=self.sec1_row)
                            for column in columns['member']] )
        if columns['has_proxy'].fetch_data(excel_row):
            self.members.append(
                    [Cell(excel_row, column, backup_row=self.sec1_row)
                            for column in columns['proxy']] )
        
    def migrate(self):
        # accountname shall be the first element of member.cells
        new_account = models.Account.objects.create(name = self.cells[0].data)
        for cell in self.cells:
            cell.migrate(new_account)
        new_account.save()

        for member_cells in self.members:
            # username shall be the first element of member.cells
            # member must be saved first, so phones etc. can be migrated
            # then it will be re-saved later after all its data is migrated
            new_user = create_unique_user(slug = member_cells[0].data)
            new_member = models.Member.objects.create(user = new_user)

            for cell in member_cells[1:]:
                cell.migrate(new_member)
            new_member.save()
            new_user.save()

            models.AccountMember.objects.create(account=new_account, 
                                                member=new_member)


# here is a slew of parser functions, used to parse excel data

def split_notes(actstr):
    ''' try to split things like  "Best Fest NEEDS SHIFT" '''
    # find last lowercase character
    if actstr == '': return '', ''
    s = len(actstr) - 1
    while s >= 0 and actstr[s] not in unicode(string.lowercase):
        s -= 1
    while s < len(actstr) and actstr[s] not in unicode(string.whitespace):
        s += 1
    if s == len(actstr) - 1: return actstr.strip(), ''
    return actstr[:s].strip(), actstr[s:].strip()

def strip_notes(a):
    return split_notes(a)[0]

def int_or_one(a):
    try:
        return int(a)
    except:
        return 1

def is_nonspace(a):
    return len(a) > 0 and not a.isspace()

def is_yes(a):
    return a.lower() == 'yes'

def split_name(namestring):
    names = namestring.strip().rsplit(None,1)
    if len(names) == 0:
        return 'Firstname', 'Lastname'
    if len(names) == 1:
        return names[0], 'Lastname'
    return names[0], names[1]

def get_first_name(a):
    return split_name(a)[0]

def get_last_name(a):
    return split_name(a)[1]

def make_username(a):
    alpha_not = re.compile(r'\W')
    ret = alpha_not.sub('', a).lower()[:8]
    if ret == '':
        return 'blanknam'
    return ret

def generate_pass(arguments_are_ignored, backup_row=None):
    return ''.join([choice(string.letters+string.digits) for i in range(8)])

def date_format(d):
    ''' for now, only fixes dates formatted as "June 15, 2008" '''
    try:
        return time.strftime('%Y-%m-%d',time.strptime(d,'"%B %d, %Y"'))
    except:
        return '1902-01-01'


# and here is a slew of porter functions, used to migrate data into the db

def create_unique_user(slug, count=0, countstr=''):
    try:
        return User.objects.create(username = slug + countstr)
    except IntegrityError:
        count += 1
        return create_unique_user(slug, count=count, countstr=str(count))

def create_phone(data, new_member):
    if data != '':
        new_member.phones.create(number = data)

def create_email(data, new_member):
    if data != '':
        new_member.emails.create(email = data)

def split_and_create_address(data, new_member):
    if data == '':
        return
    addr = data.rsplit('/',2)
    if len(addr) == 3:
        citystate = addr[1].strip().rsplit(None, 1)
        if len(citystate) == 2:
            new_member.addresses.create(
                address1 = addr[0].strip(),
                city = citystate[0].strip(),
                state = citystate[1].strip(),
                postal_code = addr[2].strip()
            )
            return
    # if problem, return entire original string as street
    new_member.addresses.create( address1 = data )


@transaction.commit_on_success
def main():
    if len(sys.argv) < 2:
        print 'Usage: %s <xl workbook>' % sys.argv[0]
        return 0

    datafile = xlrd.open_workbook(sys.argv[1])
    datasheet = datafile.sheet_by_index(0)
    headers = [unicode(x.value).strip() for x in datasheet.row(0)]
    columns = prepare_columns(headers)
    accounts = {}
    
    for n in range(1, min(datasheet.nrows, MAXLINES)):
        excel_row = datasheet.row(n) 
        section = columns['section'].fetch_data(excel_row)
        account_name = columns['account_name'].fetch_data(excel_row)
        result = 'loaded row'
        
        if section == '1.0':
            assert account_name not in accounts
            accounts[account_name] = PortAccount(excel_row, columns)
        elif section == '4.0' and account_name in accounts:
            accounts[account_name].add_sec4_row(excel_row, columns)
        else:
            result = 'SKIPPED row'
        print '%s %d, section %s, account %s' % \
                (result, n, section, account_name)

    print 'Done Reading Input File!'

    for account_name, account in accounts.iteritems():
        account.migrate()
        print 'Saved account %s' % account_name

main()
