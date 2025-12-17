from datetime import date, datetime, timedelta
from collections import defaultdict

from .types import Shift, Punch, PunchProblem


def get_date(periodBegin, count) -> str:
    monday = datetime.strptime(periodBegin, '%Y-%m-%d')
    return (monday + timedelta(days=count)).strftime("%Y-%m-%d")

def six_days_before(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = dt - timedelta(days=6)
    return new_date.strftime("%Y-%m-%d")

def get_shifts(conn, employees, periodBegin='1900-01-01', periodEnd = '2999-01-01'):
    cursor = None
    try:
        dic = defaultdict(list)
        if not employees:
            return dic
        placeholders = ",".join(["?"] * len(employees))
        cursor = conn.cursor()
        sql = (
            f"select btrustid, periodbegin, MondayBegin, mondayend, TuesdayBegin, tuesdayend, wednesdayBegin, wednesdayend, thursdayBegin, thursdayend, fridayBegin, fridayend, saturdayBegin, saturdayend, sundayBegin, sundayend, lunchminute"
            f" from sysshift inner join SysShiftDetail on sysshift.id=SysShiftDetail.shiftid inner join sysuser on sysuser.id = userid"
            f" where periodBegin >= ? and periodBegin <= ?"
            f" and btrustid in ({placeholders})"
        )
        cursor.execute(sql, six_days_before(periodBegin), periodEnd, *employees)
        rows = cursor.fetchall()
        for row in rows:
            for i in range(7):
                date = get_date(row[1], i)
                if date >= periodBegin and date <= periodEnd:
                    shift = Shift(date, row[(i + 1) * 2], row[(i + 1) * 2 + 1], row[-1])
                    dic[row[0]].append(shift)
        return dic
    finally:
        if cursor:
            cursor.close()

def get_time(row) -> str:
    hour, minute = row[2] if row[2] else "00", row[3] if row[3] else "00"
    if len(hour) == 1:
        hour = '0' + hour
    if len(minute) == 1:
        minute = '0' + minute
    return hour + ':' + minute

def get_punches(conn, employees, periodBegin='1900-01-01', periodEnd = '2999-01-01'):
    cursor = None
    try:
        dic = defaultdict(list)
        if not employees:
            return dic
        placeholders = ",".join(["?"] * len(employees))
        cursor = conn.cursor()
        sql = f"select btrustid, punchdate, hour, minute from syspunch where punchdate >= ? and punchdate <= ? and btrustid in ({placeholders})"
        cursor.execute(sql, periodBegin, periodEnd, *employees)
        rows = cursor.fetchall()
        for row in rows:
            date = row[1]
            punch = Punch(date, get_time(row))
            dic[row[0]].append(punch)
        return dic
    finally:
        if cursor:
            cursor.close()

def get_punch_problems(conn, employees, periodBegin='1900-01-01', periodEnd = '2999-01-01'):
    cursor = None
    try:
        dic = defaultdict(list)
        if not employees:
            return dic
        placeholders = ",".join(["?"] * len(employees))
        cursor = conn.cursor()
        sql = f"select btrustid, punchdate, realtotalhours from syspunchproblem where punchdate >= ? and punchdate <= ? and btrustid in ({placeholders})"
        cursor.execute(sql, periodBegin, periodEnd, *employees)
        rows = cursor.fetchall()
        for row in rows:
            punch = PunchProblem(row[1], row[2])
            dic[row[0]].append(punch)
        return dic
    finally:
        if cursor:
            cursor.close()

def get_minutes(s: str) -> int:
    if len(s) != 5 or s[2] != ':':
        return -1
    return int(s[:2]) * 60 + int(s[3:])

def calculate(punchBegin, punchEnd, shiftBegin, shiftEnd) -> int:
    # 判断开始时间 大于shiftbegin 10分钟以内，算等于
    # 没排班的话，规整到后面的15分钟整数
    if punchBegin <= shiftBegin + 10 and punchBegin > shiftBegin:
        punchBegin = shiftBegin
    elif punchBegin >= shiftBegin - 30 and punchBegin <= shiftBegin:
        punchBegin = shiftBegin
    else:
        remain = punchBegin % 15
        punchBegin += (15 - remain) % 15
    if punchEnd >= shiftEnd - 5 and punchEnd <= shiftEnd:
        punchEnd = shiftEnd
    elif punchEnd > shiftEnd:
        giveIn = (punchEnd + 5) // 30
        punchEnd = giveIn * 30
    else:
        remain = punchEnd % 15
        punchEnd -= remain
    return punchEnd - punchBegin

def check_lunch_time(minutes, lunchMinute) -> int:
    if lunchMinute == 60:
        if minutes >= 5.5 * 60:
            return minutes - 60
    elif lunchMinute == 30:
        if minutes >= 5.5 * 60 and minutes < 10 * 60:
            return minutes - 30
        elif minutes >= 10 * 60:
            return minutes - 60
    return minutes

def get_total_hours(punches: list[Punch], shift = None) -> int:
    lunchMinute = 30
    if shift:
        lunchMinute = shift.lunchMinute
    punchBegin, punchEnd = -1, -1
    for punch in punches:
        time = get_minutes(punch.time)
        if time != -1 and (punchBegin == -1 or punchBegin > time):
            punchBegin = time
        if time != -1 and (punchEnd == -1 or punchEnd < time):
            punchEnd = time
    if punchBegin == -1 or punchEnd == -1:
        return 0
    minutes = punchEnd - punchBegin
    if shift:
        minutes = calculate(punchBegin, punchEnd, get_minutes(shift.begin), get_minutes(shift.end))
    minutes = check_lunch_time(minutes, lunchMinute)
    return round(minutes / 60, 2)

def calculate_hours(shifts: list, punches: list, punchProblems: list) -> int:
    dic_shift = {}
    dic_punch = defaultdict(list)
    dic_punch_problem = {}
    dates = set()
    totalHours = 0
    for shift in shifts:
        dic_shift[shift.date] = shift
    for punch in punches:
        dic_punch[punch.date].append(punch)
        dates.add(punch.date)
    for punch_problem in punchProblems:
        dic_punch_problem[punch_problem.date] = punch_problem
        dates.add(punch_problem.date)
    for date in dates:
        if date in dic_punch_problem:
            totalHours += dic_punch_problem[date].totalHours
        elif date in dic_punch:
            punches = dic_punch[date]
            if date in dic_shift:
                totalHours += get_total_hours(punches, dic_shift[date])
            else:
                totalHours += get_total_hours(punches)
    return totalHours

def calculate_hours_by_shifts(shifts, punches, punchProblems) -> int:
    dic_shift = {s.date: s for s in shifts}
    dic_punch = defaultdict(list)
    dic_problem = {p.date: p for p in punchProblems}

    for punch in punches:
        dic_punch[punch.date].append(punch)

    total = 0

    for date, shift in dic_shift.items():
        if date in dic_problem:
            total += dic_problem[date].totalHours
        elif date in dic_punch:
            total += get_total_hours(dic_punch[date], shift)

    return total

def get_person_hours(conn, employees, periodBegin, periodEnd) -> dict:
    """
    按【排班 打卡 打卡问题处理】来统计员工工时
    """
    try:
        dic_hours = {}
        shifts_dic = get_shifts(conn, employees, periodBegin, periodEnd)
        punches_dic = get_punches(conn, employees, periodBegin, periodEnd)
        punch_problems_dic = get_punch_problems(conn, employees, periodBegin, periodEnd)
        for emp in employees:
            shifts = shifts_dic.get(emp, [])
            punches = punches_dic.get(emp, [])
            punch_problems = punch_problems_dic.get(emp, [])
            total_hours = calculate_hours(shifts, punches, punch_problems)
            dic_hours[emp] = total_hours
        return dic_hours
    except Exception as e:
        raise

def get_department_hours(conn, departments, periodBegin, periodEnd) -> dict:
    """
    按【历史排班归属】统计部门工时
    """
    cursor = None
    try:
        result = {}

        if not departments:
            return result

        cursor = conn.cursor()

        dept_placeholders = ",".join(["?"] * len(departments))

        # 1️⃣ 查该部门在时间段内的排班（拿到 departmentId + btrustid）
        sql = f"""
            select 
                d.id as departmentId,
                u.btrustid,
                s.periodBegin,
                sd.MondayBegin, sd.MondayEnd,
                sd.TuesdayBegin, sd.TuesdayEnd,
                sd.WednesdayBegin, sd.WednesdayEnd,
                sd.ThursdayBegin, sd.ThursdayEnd,
                sd.FridayBegin, sd.FridayEnd,
                sd.SaturdayBegin, sd.SaturdayEnd,
                sd.SundayBegin, sd.SundayEnd,
                sd.lunchminute
            from sysshift s
            inner join sysdepartment d on s.departmentid = d.id
            inner join SysShiftDetail sd on s.id = sd.shiftid
            inner join sysuser u on u.id = s.userid
            where d.id in ({dept_placeholders})
              and s.periodBegin >= ?
              and s.periodBegin <= ?
        """

        cursor.execute(
            sql,
            (*departments, six_days_before(periodBegin), periodEnd)
        )

        rows = cursor.fetchall()

        # department -> employee -> shifts
        dept_emp_shifts = defaultdict(lambda: defaultdict(list))
        all_emps = set()

        for row in rows:
            dept_id = row[0]
            btrustid = row[1]
            period_begin = row[2]

            for i in range(7):
                date = get_date(period_begin, i)
                if periodBegin <= date <= periodEnd:
                    shift = Shift(
                        date,
                        row[(i + 1) * 2],
                        row[(i + 1) * 2 + 1],
                        row[-1]
                    )
                    dept_emp_shifts[dept_id][btrustid].append(shift)
                    all_emps.add(btrustid)

        # 2️⃣ 批量查 punch / punchproblem
        punches_dic = get_punches(conn, list(all_emps), periodBegin, periodEnd)
        punch_problem_dic = get_punch_problems(conn, list(all_emps), periodBegin, periodEnd)

        # 3️⃣ 计算 & 汇总
        for dept_id, emp_shifts in dept_emp_shifts.items():
            total = 0
            persons = {}

            for emp, shifts in emp_shifts.items():
                punches = punches_dic.get(emp, [])
                problems = punch_problem_dic.get(emp, [])
                hours = calculate_hours_by_shifts(shifts, punches, problems)
                persons[emp] = hours
                total += hours

            result[dept_id] = {
                "total_hours": total,
                "persons": persons
            }

        return result

    finally:
        if cursor:
            cursor.close()
