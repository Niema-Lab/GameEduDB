#! /usr/bin/env python3
'''
Build a Markdown file from the GameEduDB contents
'''

# imports
from pathlib import Path
from sys import argv
import re

# constants
REQUIRED_META = { # required metadata (`None` means >0)
    'institutions': {
        'description': None,
        'location': 1,
        'name': 1,
        'url': 1,
    },
    'departments': {
        'institution_id': 1,
        'name': 1,
        'url': 1,
    },
    'programs': {
        'institution_id': 1,
        'name': 1,
        'url': 1,
    },
    'courses': {
        #'categories': None, # TODO uncomment once we've added categories to all existing courses
        'description': None,
        'institution_id': 1,
        'name': 1,
        'url': 1,
    },
}
TRANSLATE = { # translate keys to human-readable strings
    'abbreviation':         "Abbreviation",
    'categories':           "Categories",
    'course_code':          "Course Code",
    'course_id':            "Course ID",
    'course_ids':           "Course IDs",
    'courses':              "Courses",
    'credits':              "Credits",
    'credit_system':        "Credit/Unit System",
    'degree':               "Degree Type",
    'department':           "Department",
    'department_id':        "Department ID",
    'department_ids':       "Department IDs",
    'description':          "Description",
    'institution':          "Institution",
    'institution_id':       "Institution ID",
    'institution_ids':      "Institution IDs",
    'length':               "Expected Length (years)",
    'level':                "Academic Level",
    'location':             "Location",
    'name':                 "Name",
    'prerequisite_courses': "Prerequisites",
    'program_code':         "Program Code",
    'total_credits':        "Total Credits/Units",
    'url':                  "URL",
}

# key for natural sort (attempt numeric, but default to alphabetic)
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

# check data for validity
def check_data(data):
    # check required metadata
    for k in data:
        for entry_id, entry_data in data[k].items():
            for meta, meta_num in REQUIRED_META[k].items():
                if meta not in entry_data:
                    raise ValueError(f"'{k}' entry missing required '{meta}.txt' metadata: {entry_id}")
                if (meta_num is not None) and (len(entry_data[meta]) != meta_num):
                    raise ValueError(f"'{k}' entry's '{meta}.txt' has {len(entry_data[meta])} line(s) instead of {meta_num}")

    # check that all mentioned courses exist and that every course is mentioned somewhere
    mentioned_course_ids = set()
    for program_id, program_data in data['programs'].items():
        for mentioned_course_id in program_data['course_ids']:
            if mentioned_course_id not in data['courses']:
                raise ValueError(f"Missing course (mentioned in program '{program_id}'): {mentioned_course_id}")
            mentioned_course_ids.add(mentioned_course_id)
    for course_id, course_data in data['courses'].items():
        for k in ['prerequisite_course_ids']:
            if k in course_data:
                for mentioned_course_id in course_data[k]:
                    if mentioned_course_id not in data['courses']:
                        raise ValueError(f"Missing course (mentioned in '{k}' of course '{course_id}'): {mentioned_course_id}")
                    mentioned_course_ids.add(mentioned_course_id)
    for course_id in data['courses']:
        if course_id not in mentioned_course_ids:
            raise ValueError(f"Course not mentioned anywhere: {course_id}")

# sort institution IDs by name
def sort_institution_ids(institution_ids, data):
    return sorted(set(institution_ids), key=lambda x: data['institutions'][x]['name'])

# sort department IDs by name
def sort_department_ids(department_ids, data):
    department_ids = set(department_ids)
    has_none = None in department_ids
    out = sorted(department_ids-{None}, key=lambda x: data['departments'][x]['name'])
    if has_none:
        out += [None]
    return out

# sort program IDs by name
def sort_program_ids(program_ids, data):
    return sorted(set(program_ids), key=lambda x: data['programs'][x]['name'])

# sort course IDs by course code (attempt numeric sort)
def sort_course_ids(course_ids, data):
    sort_keys = {course_id: data['courses'][course_id]['name'][0] for course_id in set(course_ids)}
    for course_id in set(sort_keys.keys()):
        if 'course_code' in data['courses'][course_id]:
            sort_keys[course_id] = data['courses'][course_id]['course_code'][0]
    return sorted(sort_keys.keys(), key=lambda x: natural_sort_key(sort_keys[x]))

# build Markdown
def build_markdown(data):
    # set things up
    out = ''
    institution_to_programs = {institution_id: set() for institution_id in data['institutions']}
    institution_to_departments = {institution_id: set() for institution_id in data['institutions']}
    for program_id, program_data in data['programs'].items():
        institution_to_programs[program_data['institution_id'][0]].add(program_id)
    for department_id, department_data in data['departments'].items():
        institution_to_departments[department_data['institution_id'][0]].add(department_id)
    institution_to_courses = dict()
    for course_id, course_data in data['courses'].items():
        institution_id = course_data['institution_id'][0]
        if institution_id not in institution_to_courses:
            institution_to_courses[institution_id] = dict()
        if 'department_id' in course_data:
            department_id = course_data['department_id'][0]
        else:
            department_id = None
        if department_id not in institution_to_courses[institution_id]:
            institution_to_courses[institution_id][department_id] = set()
        institution_to_courses[institution_id][department_id].add(course_id)

    # write institutions
    for institution_id in sort_institution_ids(data['institutions'].keys(), data):
        institution_data = data['institutions'][institution_id]
        out += f"# [{institution_data['name'][0]}"
        if 'abbreviation' in institution_data:
            out += f" ({' / '.join(institution_data['abbreviation'])})"
        out += f"]({institution_data['url'][0]}) {{#{institution_id}}}\n"
        out += f"{'\n\n'.join(institution_data['description'])}\n\n"
        out += f"* **{TRANSLATE['location']}:** {institution_data['location'][0]}\n"
        remaining_institution_keys = set(institution_data.keys()) - {'name', 'url', 'abbreviation', 'description', 'location'}
        for k in sorted(remaining_institution_keys, key=lambda x: TRANSLATE[x]):
            out += f"* **{TRANSLATE[k]}:** {' / '.join(institution_data[k])}\n"
        out += '\n'

        # write programs
        out += f"## Programs\n\n"
        for program_id in sort_program_ids(institution_to_programs[institution_id], data):
            program_data = data['programs'][program_id]
            out += f"### [{program_data['name'][0]}"
            if 'abbreviation' in program_data:
                out += f" ({' / '.join(program_data['abbreviation'])})"
            out += f"]({program_data['url'][0]}) {{#{program_id}}}\n"
            if 'description' in program_data:
                out += f"{'\n\n'.join(program_data['description'])}\n\n"
            out += f"* **{TRANSLATE['institution']}:** [{data['institutions'][program_data['institution_id'][0]]['name'][0]}](#{program_data['institution_id'][0]})\n"
            if 'department_id' in program_data:
                out += f"* **{TRANSLATE['department']}:** [{data['departments'][program_data['department_id'][0]]['name'][0]}](#{program_data['department_id'][0]})\n"
            remaining_program_keys = set(program_data.keys()) - {'name', 'url', 'abbreviation', 'description', 'institution_id', 'department_id', 'course_ids'}
            for k in sorted(remaining_program_keys, key=lambda x: TRANSLATE[x]):
                out += f"* **{TRANSLATE[k]}:** {' / '.join(program_data[k])}\n"
            course_category_counts = dict()
            for course_id in program_data['course_ids']:
                if 'categories' in data['courses'][course_id]: # TODO delete this check once 'categories' becomes required for courses
                    for cat in data['courses'][course_id]['categories']:
                        if cat not in course_category_counts:
                            course_category_counts[cat] = 0
                        course_category_counts[cat] += 1
            if len(course_category_counts) != 0: # TODO delete this check once 'categories' becomes required for courses
                out += f"* **{TRANSLATE['categories']}:**\n"
                for cat, cat_count in sorted(course_category_counts.items(), key=lambda x: (x[1],x[0]), reverse=True):
                    out += f"    * {cat}: {cat_count} of {len(program_data['course_ids'])} ({round(100 * cat_count / len(program_data['course_ids']))}%)\n"
            out += f"* **{TRANSLATE['courses']}:**\n"
            for course_id in sort_course_ids(program_data['course_ids'], data):
                out += "    * ["
                if 'course_code' in data['courses'][course_id]:
                    out += f"{data['courses'][course_id]['course_code'][0]}: "
                out += f"{data['courses'][course_id]['name'][0]}](#{course_id})\n"
            out += '\n'

        # write departments
        out += f"## Departments\n\n"
        for department_id in sort_department_ids(institution_to_courses[institution_id].keys(), data):
            if department_id is None:
                out += "### No Department\n\n"
            else:
                department_data = data['departments'][department_id]
                out += f"### [{department_data['name'][0]}"
                if 'abbreviation' in department_data:
                    out += f" ({' / '.join(department_data['abbreviation'])})"
                out += f"]({department_data['url'][0]}) {{#{department_id}}}\n"
                if 'description' in department_data:
                    out += f"{'\n\n'.join(department_data['description'])}\n\n"
                out += f"* **{TRANSLATE['institution']}:** [{data['institutions'][department_data['institution_id'][0]]['name'][0]}](#{department_data['institution_id'][0]})\n"
                remaining_department_keys = set(department_data.keys()) - {'name', 'url', 'abbreviation', 'description', 'institution_id'}
                for k in sorted(remaining_department_keys, key=lambda x: TRANSLATE[x]):
                    out += f"* **{TRANSLATE[k]}:** {' / '.join(department_data[k])}\n"
                out += '\n'

            # write courses
            for course_id in sort_course_ids(institution_to_courses[institution_id][department_id], data):
                course_data = data['courses'][course_id]
                out += "#### ["
                if 'course_code' in course_data:
                    out += f"{course_data['course_code'][0]}: "
                out += f"{course_data['name'][0]}]({course_data['url'][0]}) {{#{course_id}}}\n"
                out += f"{'\n\n'.join(course_data['description'])}\n\n"
                out += f"* **{TRANSLATE['institution']}:** [{data['institutions'][course_data['institution_id'][0]]['name'][0]}](#{course_data['institution_id'][0]})\n"
                if 'department_id' in course_data:
                    out += f"* **{TRANSLATE['department']}:** [{data['departments'][course_data['department_id'][0]]['name'][0]}](#{course_data['department_id'][0]})\n"
                if 'prerequisite_course_ids' in course_data:
                    prereq_key = {prereq_course_id: data['courses'][prereq_course_id]['name'][0] for prereq_course_id in set(course_data['prerequisite_course_ids'])}
                    for prereq_course_id in set(prereq_key.keys()):
                        if 'course_code' in data['courses'][prereq_course_id]:
                            prereq_key[prereq_course_id] = data['courses'][prereq_course_id]['course_code'][0]
                    out += f'''* **{TRANSLATE['prerequisite_courses']}:** {' / '.join(f'[{prereq_key[prereq_course_id]}](#{prereq_course_id})' for prereq_course_id in sorted(prereq_key.keys(), key=lambda x: natural_sort_key(prereq_key[x])))}\n'''
                remaining_course_keys = set(course_data.keys()) - {'course_code', 'name', 'url', 'description', 'institution_id', 'department_id', 'course_id', 'prerequisite_course_ids'}
                for k in sorted(remaining_course_keys, key=lambda x: TRANSLATE[x]):
                    out += f"* **{TRANSLATE[k]}:** {' / '.join(course_data[k])}\n"
                out += '\n'
    return out

# main logic
def main():
    # check GameEduDB path
    if len(argv) == 1:
        root_path = Path(argv[0]).resolve().parent.parent
    elif len(argv) == 2:
        root_path = Path(argv[1]).resolve()
    else:
        print(f"USAGE: {argv[0]} [GameEduDB_path]"); exit(1)
    courses_path = root_path / 'courses'
    departments_path = root_path / 'departments'
    institutions_path = root_path / 'institutions'
    programs_path = root_path / 'programs'
    for path in [root_path, courses_path, departments_path, institutions_path, programs_path]:
        if not path.is_dir():
            raise ValueError(f"Directory not found: {path}")

    # load data
    data = {
        data_path.name: {
            entry_path.name: {
                meta_path.stem: [
                    l.strip() for l in open(meta_path, mode='rt') if len(l.strip()) != 0
                ] for meta_path in entry_path.glob('*.txt')
            } for entry_path in data_path.glob('*') if entry_path.is_dir()
        } for data_path in [institutions_path, departments_path, courses_path, programs_path]
    }
    check_data(data)

    # build output
    out = build_markdown(data)
    if not out.endswith('\n'):
        out += '\n'
    print(out, end='')

# run script
if __name__ == "__main__":
    main()
