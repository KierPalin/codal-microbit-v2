#!/usr/bin/env python3

# The MIT License (MIT)

# Copyright (c) 2017 Lancaster University.

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import os
import re
import json
import shutil
import tempfile
import subprocess
from natsort import natsorted
from optparse import OptionParser

outFile = None
outBuffer = []
def output( data, forcePrint = False ):
    outBuffer.append( data )

    if forcePrint:
        print( data )

def writeOutput():
    if outFile != None:
        with open( outFile, mode="w", encoding="utf-8" ) as out:
            for line in outBuffer:
                out.write( f"{line}\n" )
    else:
        for line in outBuffer:
            print( line )

def getTags():
    tags = os.popen('git -P tag').read().strip().splitlines()
    tags = filter(lambda x: "-" not in x, tags)
    return natsorted(tags,reverse=True)

def getCommitsBetween( tagA, tagB = "HEAD", clone=None):
    if clone:
        # Get repo name from clone URL
        repo_name = clone.split('/')[-1]
        # Get a temp folder to clone the repo into (without files)
        original_path = os.getcwd()
        clone_path = tempfile.mkdtemp()
        os.chdir(clone_path)
        try:  
            subprocess.check_call(
                ['git', 'clone', '--bare', '--filter=blob:none', '--quiet', f'{clone}', f'{repo_name}.git'],
                stdout=subprocess.DEVNULL
            )
            os.chdir(f'{repo_name}.git')
        except Exception as e:
            os.chdir(original_path)
            print(f"Cannot access repo: {e}")
            return "\n - Unable to find commits"
    commits = os.popen(f'git log --format="%s (by %an)" --no-merges --reverse {tagA}..{tagB}').read().strip().splitlines()
    if clone:
        os.chdir(original_path)
        shutil.rmtree(clone_path)
    return "\n - ".join([""] + commits)

def getRepoURL():
    origin = os.popen("git remote get-url origin").read().strip().split( "github.com/", maxsplit=1 )
    url = f"https://github.com/{origin[1]}"
    if url.endswith("/"):
        url = url[:-1]
    return url

def getOldAndNewLibCommits(old_commit, new_commit):
    try:
        old_target_locked = json.loads(os.popen(f"git show {old_commit}:target-locked.json").read())
        new_target_locked = json.loads(os.popen(f"git show {new_commit}:target-locked.json").read())
    except:
        return {}

    lib_versions = {}
    # We only have a handful of libraries in the list, okay to be inefficient
    for old_lib in old_target_locked["libraries"]:
        for new_lib in new_target_locked["libraries"]:
            if old_lib["name"] == new_lib["name"]:
                lib_versions[old_lib["name"]] = {
                    "old": old_lib["branch"],
                    "new": new_lib["branch"],
                    "url": old_lib["url"]
                }
    return lib_versions

def outputTagDiff( repoUrl, tagOld, tagNew ):
    # Target commits
    logURL = f"{repoUrl}/compare/{tagOld}...{tagNew}"
    output( f"## [{tagNew}]({logURL})", forcePrint=True )
    output( getCommitsBetween( tagOld, tagNew ), forcePrint=True )

    # Library commits
    libInfo = getOldAndNewLibCommits( tagOld, tagNew )
    for libName, lib in libInfo.items():
        libCommits = getCommitsBetween(lib['old'], lib['new'], clone=lib['url'])
        if libCommits:
            diffUrl = f"{lib['url']}/compare/{lib['old']}...{lib['new']}"
            diffUrlMarkdown = f"[{lib['old'][:7]}...{lib['new'][:7]}]({diffUrl})"
            output(f"\n### {libName} ({diffUrlMarkdown})", forcePrint=True)
            output(libCommits, forcePrint=True)

    output( '', forcePrint=True )


tags = getTags()
repoUrl = getRepoURL()

defaultTag = "v0.0.1"
if( len(tags) > 0 ):
    defaultTag = tags[0]

parser = OptionParser()
parser.add_option( "--input", dest="inFile", help="read existing changelog from FILE", metavar="FILE" )
parser.add_option( "--output", dest="outFile", help="write updated changelog to FILE", metavar="FILE" )
parser.add_option( "--tag", dest="tag", help="Force this to be the tag to update to", default=defaultTag )

(options, args) = parser.parse_args()

if options.tag not in tags:
    print( f"No such tag '{options.tag}' found, unable to continue." )
    exit( 1 )

outFile = options.inFile if options.outFile == None else options.outFile

output( '# Changelog' )
output( '*The head of this file is autogenerated and will be overwritten on the next tag.*\n' )
output( 'For official release notes, please see Releases.md\n' )
output( 'The current tag uses the following library versions:' )
config = json.loads(open( 'target-locked.json' ).read())
for lib in config['libraries']:
    output( f" - {lib['name']} = {lib['url']}/tree/{lib['branch']}" )
output( '' )

if options.inFile != None:
    # Read the existing changelog and only add a new section for the new tag
    with open( options.inFile, mode="r", encoding="utf-8" ) as input_changelog:
        input_changelog_lines = input_changelog.readlines()

    lastTag = ''
    try:
        for line in input_changelog_lines:
            line = line.replace( "\n", "" )
            if lastTag:
                output( line )
            elif line.startswith( "##" ):
                matches = re.search( "\[(v.+)\]", line )
                lastTag = matches.group(1)
                if lastTag == options.tag:
                    print( "Nothing to do, Stop." )
                    exit( 0 )
                outputTagDiff( repoUrl, lastTag, options.tag )
                output( line )
    except Exception as e:
        print("Error:")
        print(e)
        exit( 1 )

else:
    # Generate a new changelog from scratch
    for i in range(0, len(tags)-1):
        outputTagDiff( repoUrl, tags[i+1], tags[i] )

writeOutput()
exit( 0 )
