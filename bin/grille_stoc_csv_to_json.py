#! /usr/bin/env python3

import csv
import json
import sys
import uuid
from datetime import datetime


OUTPUT_TEMPLATE_HEAD = '.output.{}.json'
MONGOIMPORT_USAGE_TEMPLATE = """
    for a in {}
    do echo "importing $a..."
    mongoimport --db vigiechiro --collection grille_stoc --file $a --jsonArray
    done
"""


def main(in_file):
    output_template = in_file + OUTPUT_TEMPLATE_HEAD
    timestamp = datetime.now().timestamp()
    with open(in_file, 'r') as fd:
        reader = csv.reader(fd, delimiter=';')
        _ = next(reader)
        file_count = 0
        while True:
            out_file = output_template.format(file_count)
            output = open(out_file, 'w')
            print('creating file {}'.format(out_file))
            output.write('[\n')
            first = True
            buffer_size = 0
            for line in reader:
                if not first:
                    output.write(',\n')
                else:
                    first = False
                document = {
                    "_updated": {"$date": timestamp},
                    "_created": {"$date": timestamp},
                    "_etag": uuid.uuid4().hex,
                    "centre": {
                        "type": "Point",
                        "coordinates": [float(x) for x in line[:2]]
                    },
                    "numero": line[2]
                }
                document = json.dumps(document)
                buffer_size += len(document)
                output.write(document)
                if buffer_size > 15000000:
                    file_count += 1
                    break
            output.write(']\n')
            output.close()
            if not any(reader):
                break


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage : {} carrenat_wgs84_centroids.csv'.format(sys.argv[0]))
    main(sys.argv[1])
    print("To import generated json using mongoimport, use the following commands :")
    print(MONGOIMPORT_USAGE_TEMPLATE.format(sys.argv[1] + OUTPUT_TEMPLATE_HEAD.format('*')))
