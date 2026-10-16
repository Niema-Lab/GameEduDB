#! /usr/bin/env python3
'''
Build a Markdown file from the GameEduDB contents
'''

# imports
from pathlib import Path
from sys import argv

# constants
REQUIRED_META = { # required metadata (`None` means >0)
    'institutions': { # TODO
        'name': 1,
        'url': 1,
        'description': None,
    },
    'departments': { # TODO
        'name': 1,
        'url': 1,
        'institution_id': 1
    },
    'programs': { # TODO
        'name': 1,
        'url': 1,
        'institution_id': 1,
    },
    'courses': {
        'name': 1,
        'course_code': 1,
        'url': 1,
        'description': None,
        'institution_id': 1,
    },
}
TRANSLATE = { # translate keys to human-readable strings
    'abbreviation':    "Abbreviation",
    'course_code':     "Course Code",
    'course_id':       "Course ID",
    'course_ids':      "Course IDs",
    'credit_system':   "Credit/Unit System",
    'degree':          "Degree Type",
    'department_id':   "Department ID",
    'department_ids':  "Department IDs",
    'description':     "Description",
    'institution_id':  "Institution ID",
    'institution_ids': "Institution IDs",
    'length':          "Expected Length (years)",
    'level':           "Academic Level",
    'name':            "Name",
    'program_code':    "Program Code",
    'total_credits':   "Total Credits/Units",
    'url':             "URL",
}

# check data for validity
def check_data(data):
    for k in data:
        for entry_id, entry_data in data[k].items():
            for meta, meta_num in REQUIRED_META[k].items():
                if meta not in entry_data:
                    raise ValueError(f"'{k}' entry missing required '{meta}.txt' metadata: {entry_id}")
                if (meta_num is not None) and (len(entry_data[meta]) != meta_num):
                    raise ValueError(f"'{k}' entry's '{meta}.txt' has {len(entry_data[meta])} line(s) instead of {meta_num}")

# sort department IDs by name
def sort_department_ids(department_ids, data):
    return sorted(department_ids, key=lambda x: data['departments'][x]['name'])

# sort program IDs by name
def sort_program_ids(program_ids, data):
    return sorted(program_ids, key=lambda x: data['programs'][x]['name'])

# sort course IDs by course code, but require a course's prerequisites to come before it
def sort_course_ids(course_ids, data):
    return sorted(course_ids) # TODO REPLACE WITH ACTUAL IMPLEMENTATION

# build Markdown
def build_markdown(data):
    # precompute mappings
    institution_to_departments = dict()
    department_to_programs = dict()
    for mapping_dict, child_key, parent_id_key in [
        (institution_to_departments, 'departments', 'institution_id'),
        (department_to_programs, 'programs', 'department_id'),
    ]:
        for child_id, child_data in data[child_key].items():
            parent_id = child_data[parent_id_key][0]
            if parent_id not in mapping_dict:
                mapping_dict[parent_id] = set()
            mapping_dict[parent_id].add(child_id)

    # create Markdown
    out = ''
    for institution_id, institution_data in sorted(data['institutions'].items(), key=lambda x: x[1]['name']):
        # institution info
        out += f"# [{institution_data['name'][0]}]({institution_data['url'][0]})"
        if 'abbreviation' in institution_data:
            out += f" ({' / '.join(institution_data['abbreviation'])})"
        out += f" {{#{institution_id}}}\n"
        out += f"{'\n\n'.join(institution_data['description'])}\n\n"
        remaining_institution_keys = set(institution_data.keys()) - {'name', 'url', 'abbreviation', 'description'}
        if len(remaining_institution_keys) != 0:
            for k in sorted(remaining_institution_keys, key=lambda x: TRANSLATE[x]):
                out += f"* **{TRANSLATE[k]}:** {' / '.join(institution_data[k])}\n"
            out += '\n'
        institution_departments = institution_to_departments[institution_id]
        if len(institution_departments) == 0:
            raise NotImplementedError(f"TODO NIEMA: Handle institution without any departments: {institution_id}") # TODO
        else:
            # department info
            for department_id in sort_department_ids(institution_to_departments[institution_id], data):
                department_data = data['departments'][department_id]
                out += f"## [{department_data['name'][0]}]({department_data['url'][0]})"
                if 'abbreviation' in department_data:
                    out += f" ({' / '.join(department_data['abbreviation'])})"
                out += f" {{#{department_id}}}\n"
                if 'description' in department_data:
                    out += f"{'\n\n'.join(department_data['description'])}\n\n"
                remaining_department_keys = set(department_data.keys()) - {'name', 'url', 'abbreviation', 'description', 'institution_id'}
                if len(remaining_department_keys) != 0:
                    for k in sorted(remaining_department_keys, key=lambda x: TRANSLATE[x]):
                        out += f"* **{TRANSLATE[k]}:** {' / '.join(department_data[k])}\n"
                    out += '\n'
                for program_id in sort_program_ids(department_to_programs[department_id], data):
                    # program info
                    program_data = data['programs'][program_id]
                    out += f"### [{program_data['name'][0]}]({program_data['url'][0]})"
                    if 'abbreviation' in program_data:
                        out += f" ({' / '.join(program_data['abbreviation'])})"
                    out += f" {{#{program_id}}}\n"
                    if 'description' in program_data:
                        out += f"{'\n\n'.join(program_data['description'])}\n\n"
                    remaining_program_keys = set(program_data.keys()) - {'name', 'url', 'abbreviation', 'description', 'institution_id', 'department_id', 'course_ids'}
                    if len(remaining_program_keys) != 0:
                        for k in sorted(remaining_program_keys, key=lambda x: TRANSLATE[x]):
                            out += f"* **{TRANSLATE[k]}:** {' / '.join(program_data[k])}\n"
                        out += '\n'
                    for course_id in sort_course_ids(program_data['course_ids'], data):
                        course_data = data['courses'][course_id]
                        out += f"#### [{course_data['course_code'][0]}: {course_data['name'][0]}]({course_data['url'][0]})\n"
                        out += f"{'\n\n'.join(course_data['description'])}\n\n"
                        remaining_course_keys = set(course_data.keys()) - {'course_code', 'name', 'url', 'description', 'institution_id', 'department_id', 'course_id'}
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
