import functools
from collections import defaultdict
import pyodbc


def get_shifts(conn, employees):
    try:
        dic = defaultdict(list)
        if not employees:
            return dic
        btrustids = "','".join(employees)
        cursor = conn.cursor()
        sql = f"select btrustid, periodbegin, MondayBegin, mondayend, TuesdayBegin, tuesdayend, wednesdayBegin, wednesdayend, thursdayBegin, thursdayend, fridayBegin, fridayend, saturdayBegin, saturdayend, sundayBegin, sundayend, lunchminute from sysshift inner join sysdepartment on departmentid = sysdepartment.id inner join SysShiftDetail on sysshift.id=SysShiftDetail.shiftid inner join sysuser on sysuser.id = userid where btrustid in ('{btrustids}')"
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            for i in range(7):
                date = get_date(row[1], i)
                shift = Shift(date, row[(i + 1) * 2], row[(i + 1) * 2 + 1], row[-1])
                dic[row[0]].append(shift)
        return dic
    finally:
        cursor.close()
        conn.close()