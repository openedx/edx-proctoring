#####################################################################################
# This is the script to manually generate obscured_user_id for proctoring
# providers based on updated settings secret. The script takes in two required
# positional arguments (input_file_path) and (output_file_path). An optional
# argument of (backend) can also be specified for the specific proctoring_backend
#
# The script also needs OS environment variables "PROCTORING_USER_OBFUSCATION_KEY"
# and "DJANGO_SECRET_KEY" set. The script needs these to generate the obscured user_ids
# For example usage:
#   python obscure_user.py input_users.txt output.txt --backend proctortrack
#
#####################################################################################

import argparse
import csv
import hashlib
import hmac
import os

PROCTORING_USER_OBFUSCATION_KEY = None
SECRET_KEY = None


def obscured_user_id(secret_key, user_id, *extra):
    """
    Obscures the user id, returning a sha1 hash
    Any extra information can be added to the hash
    """

    obs_hash = hmac.new(secret_key.encode('ascii'), digestmod=hashlib.sha1)
    obs_hash.update(str(user_id).encode('utf-8'))
    obs_hash.update(b''.join(str(ext).encode('utf-8') for ext in extra))
    return obs_hash.hexdigest()


def run():
    parser = argparse.ArgumentParser(
        description='Take a csv file with its user_ids and output a csv file with its obscured_user_id'
    )
    parser.add_argument(
        'input_file_path',
        help='The file path with user_ids listed. It should be an CSV file'
    )
    parser.add_argument(
        'output_file_path',
        help='The file path with outputed obscure_user_ids added'
    )
    backend_help = """The proctoring backend we are obscuring the IDs for.
        Two choices: 'proctortrack' or 'software_secure'.
        Default is 'proctortrack'"""

    parser.add_argument(
        '--backend',
        default='proctortrack',
        help=backend_help
    )

    args = parser.parse_args()
    PROCTORING_USER_OBFUSCATION_KEY = os.environ.get('PROCTORING_USER_OBFUSCATION_KEY')
    SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
    backend = args.backend

    if not PROCTORING_USER_OBFUSCATION_KEY or not SECRET_KEY:
        instruction_text = """You do not have needed environment variable set.
            Please set both PROCTORING_USER_OBFUSCATION_KEY and DJANGO_SECRET_KEY
            into your environment"""
        print(instruction_text)
        return

    if not args.input_file_path:
        print("Please specify input file path of the CSV file containing user_ids")
        return

    if not args.output_file_path:
        print("Please specify output file path of the CSV file containing obscured_user_ids")

    conversion_dict = {}
    row_counter = 0

    # injest the input csv file and store the data in memory
    with open(args.input_file_path) as input_csv:
        file_reader = csv.DictReader(input_csv)
        for row in file_reader:
            row_counter += 1
            email = row.get('email')
            user_id = row.get('user_id')
            if not (user_id and email):
                print('we have row {} we cannot read! Skipped'.format(row_counter))
                continue
            conversion_dict[email] = user_id

    # output the obscured user ids into the output file specified.
    with open(args.output_file_path, 'w') as output_csv:
        fieldnames = ['email', 'existing_user_id', 'target_user_id']
        writer = csv.DictWriter(output_csv, fieldnames=fieldnames)
        writer.writeheader()
        for email, user_id in conversion_dict.items():
            existing_user_id = obscured_user_id(SECRET_KEY, user_id, backend)
            target_user_id = obscured_user_id(PROCTORING_USER_OBFUSCATION_KEY, user_id, backend)
            writer.writerow({
                'email': email,
                'existing_user_id': existing_user_id,
                'target_user_id': target_user_id
            })


if __name__ == "__main__":
    run()
