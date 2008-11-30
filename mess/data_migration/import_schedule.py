import sys
from os.path import dirname, abspath
sys.path.append(dirname(dirname(abspath(__file__))))
import settings
from django.core.management import setup_environ
setup_environ(settings)

import xlrd
from xlrd import empty_cell
import datetime

from scheduling.models import *
from membership.models import *


def make_job(row, book):
    'minimally validate and create jobs from sheet rows'
    if row[0].ctype != xlrd.XL_CELL_NUMBER:
        print "rejecting row:"
        print row
        return
    job = Job(id = row[0].value, name = row[1].value)
    if row[3].ctype == xlrd.XL_CELL_TEXT:
        job.description = row[3].value
    if row[4].ctype == xlrd.XL_CELL_NUMBER:
        job.type = row[4].value
    if row[5].ctype == xlrd.XL_CELL_NUMBER:
        job.freeze_days = row[5].value
    if row[6].ctype == xlrd.XL_CELL_NUMBER:
        job.hours_multiplier = row[6].value

    job.save()
    print job

# if columns were addressable by label, this would collapse easily with the other func
def make_task_fmt2(row, book):
    'minimally validate and load format 2 tasks'
    isoTimeFmt = "%Y-%m-%dT%H:%M"
    
    if row[0].ctype != xlrd.XL_CELL_NUMBER:
        print "rejecting row: ", row
        return

    if row[1].ctype != xlrd.XL_CELL_DATE:
        print "format 2 handler got format 1 row" 
        return

    job = Job.objects.get(id = row[0].value)

    start_day = datetime.datetime(*xlrd.xldate_as_tuple(row[1].value, book.datemode))
    start_time_tup = xlrd.xldate_as_tuple(row[2].value, book.datemode)
    print start_time_tup
    start_time = datetime.time(*start_time_tup[3:]) #slice out just the time part

    start = datetime.datetime.combine(start_day, start_time)

    task = Task(
            job = job,
            start = start,
            hours = str(row[4].value),
            recurrence_unit = row[6].value.lower(),
            recurrence_freq = row[7].value,
            )
    try:
        member = Member.objects.get(user__username = row[8].value)
        account = Account.objects.get(name = row[9].value)
        task.member = member
        task.account = account
    except Member.DoesNotExist, Account.DoesNotExist:
        pass

    try:
        task.deadline = datetime.datetime.strptime(row[3].value, isoTimeFmt)
    except:
        pass
    
    task.save()
    print task

def make_task_fmt1(row, book):
    'minimally validate and load format 1 tasks'
    isoTimeFmt = "%Y-%m-%dT%H:%M"
    
    if row[0].ctype != xlrd.XL_CELL_NUMBER:
        print "rejecting row: ", row
        return

    if row[1].ctype != xlrd.XL_CELL_TEXT:
        print "format 1 handler got format 2 row" 
        return

    job = Job.objects.get(id = row[0].value)
    start = datetime.datetime.strptime(row[1].value, isoTimeFmt)

    task = Task(
            job = job,
            start = start,
            hours = str(row[3].value),
            recurrence_unit = row[5].value.lower(),
            recurrence_freq = row[6].value,
            )
    try:
        member = Member.objects.get(user__username = row[7].value)
        account = Account.objects.get(name = row[8].value)
        task.member = member
        task.account = account
    except Member.DoesNotExist, Account.DoesNotExist:
        pass

    try:
        task.deadline = datetime.datetime.strptime(row[2].value, isoTimeFmt)
    except:
        pass
    
    task.save()
    print task

def dispatch_rows(sheet, book):
    print "processing %s" % sheet.name
        
    if sheet.name == u"Jobs":
        handler = make_job
    if sheet.name.find('Shift Sch') >= 0:
        if sheet.name.find('Fmt1') >= 0:
            handler = make_task_fmt1
        else:
            handler = make_task_fmt2

    for i in range(1, sheet.nrows):
        row = sheet.row(i)
        handler(row, book)

def main():
    'Open Workbooks, dispatch to handlers'
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print "useage: %s <xl workbook>" % sys.argv[0]
        return 0
    
    bookname = sys.argv[1]
    print "opening %s\n" % bookname
    book = xlrd.open_workbook(bookname)
    for sheet in book.sheets():
        dispatch_rows(sheet, book)

if __name__ == "__main__":
    sys.exit(main())