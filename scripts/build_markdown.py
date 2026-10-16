#! /usr/bin/env python3
'''
Build a Markdown file from the GameEduDB contents
'''

# imports
from pathlib import Path
from sys import argv

# constants
REQUIRED_META = { # `None` means "at least 1"
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
        'url': 1,
        'description': None,
        'institution_id': 1,
    },
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
            out += f" ({'/'.join(institution_data['abbreviation'])})"
        out += f" {{#{institution_id}}}\n"
        out += f"{'\n\n'.join(institution_data['description'])}\n\n"
        institution_departments = institution_to_departments[institution_id]
        if len(institution_departments) == 0:
            raise NotImplementedError(f"TODO NIEMA: Handle institution without any departments: {institution_id}") # TODO
        else:
            # department info
            for department_id in sorted(institution_to_departments[institution_id], key=lambda x: data['departments'][x]['name']):
                department_data = data['departments'][department_id]
                out += f"## [{department_data['name'][0]}]({department_data['url'][0]})"
                if 'abbreviation' in department_data:
                    out += f" ({'/'.join(department_data['abbreviation'])})"
                out += f" {{#{department_id}}}\n"
                if 'description' in department_data:
                    out += f"{'\n\n'.join(department_data['description'])}\n\n"
                for program_id in sorted(department_to_programs[department_id], key=lambda x: data['programs'][x]['name']):
                    # program info
                    program_data = data['programs'][program_id]
                    out += f"### [{program_data['name'][0]}]({program_data['url'][0]})"
                    if 'abbreviation' in program_data:
                        out += f" ({'/'.join(program_data['abbreviation'])})"
                    out += f" {{#{program_id}}}\n"
                    if 'description' in program_data:
                        out += f"{'\n\n'.join(program_data['description'])}\n\n"
                    pass # TODO CONTINUE HERE
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
