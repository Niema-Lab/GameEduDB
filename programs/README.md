This directory contains programs, which are collections of courses (e.g. degree programs, certifications, online specializations, etc.). Each individual program is contained within a folder whose name is a unique identifier for the program. Within each program's folder, the following files contain program attributes:

* `name.txt` - Official name of the program
* `abbreviation.txt` - Abbreviation of the name of the program
* `program_code.txt` - Institutional ID/code of the program
* `url.txt` - URL of the program (ideally the official program website)
* `institution_id.txt` - GameEduDB institution ID (as defined in [`institutions`](../institutions)) in which the program is offered
* `department_id.txt` - GameEduDB department ID (as defined in [`departments`](../departments)) in which the program resides
* `description.txt` - Description of the program (ideally the official description)
* `level.txt` - Academic level of the program (e.g. Associate, Bachelor, Master, Doctorate, etc.)
* `degree.txt` - Degree type (e.g. B.S., B.A., etc.)
* `length.txt` - Expected length of the program (in years)
* `credit_system.txt` - Credit/unit system (e.g. Quarter, Semester, etc.)
* `total_credits.txt` - Total number of credits/units (defined in `credit_system.txt`) to complete the program
* `course_ids.txt` - List of GameEduDB course IDs (as defined in [`courses`](../courses)) within the program
