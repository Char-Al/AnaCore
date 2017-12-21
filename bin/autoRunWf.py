#!/usr/bin/env python3
#
# Copyright (C) 2017 IUCT-O
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

__author__ = 'Frederic Escudie'
__copyright__ = 'Copyright (C) 2017 IUCT-O'
__license__ = 'GNU General Public License'
__version__ = '1.2.0'
__email__ = 'escudie.frederic@iuct-oncopole.fr'
__status__ = 'prod'

import os
import sys
import time
import datetime
import warnings
import argparse
import subprocess

CURRENT_DIR = os.path.dirname(__file__)
LIB_DIR = os.path.abspath(os.path.join(os.path.dirname(CURRENT_DIR), "lib"))
sys.path.append(LIB_DIR)
if os.getenv('PYTHONPATH') is None: os.environ['PYTHONPATH'] = LIB_DIR
else: os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + os.pathsep + LIB_DIR

from illumina import SampleSheetIO



ressources_folder = "/save/fescudie/IUCT/dev/ressources/amplicon_design"
genome = {
    'assembly': "GRCh37",
    'sequences': "/work/fescudie/bank/Homo_sapiens/DNA/GRCh37_Ensembl75_std/without_contig/Homo_sapiens.GRCh37.75.dna.woutContigs.fa"
}
workflow_path = "/save/fescudie/IUCT/WF_NAME/current/app/bin/jflow_cli.py"

########################################################################
#
# FUNCTIONS
#
########################################################################
def exec_cmd( cmd ):
    print( " ".join(cmd) )
    subprocess.check_call( cmd )

def getProtocol( in_spl_folder ):
    """
    @summary: Returns the command to launch the workflow.******************************************************
    @param in_spl_folder: [str] Path to the sample folder (containing fastq and the samplesheet).
    @return: [None/list] The command if the corresponding workflow exists and None otherwise.
    @warning: For Amplicon - DS the manifests names must be <DESIGN>_A.txt and <DESIGN>_B.txt.
    """
    protocol = {"workflow": None, "design": None}
    samplesheet = SampleSheetIO( os.path.join(in_spl_folder, "SampleSheet.csv") )
    if samplesheet.header["Application"] == "Amplicon - DS" or samplesheet.header["Workflow"] == "Amplicon - DS":
        protocol["workflow"] = "Amplicon - DS"
        manifest_A = os.path.basename(samplesheet.manifests["A"])
        protocol["design"] = manifest_A.split("_A.txt")[0]
    return protocol

def getWorkflows( protocol ):
    wf = list()
    if protocol["workflow"] == "Amplicon - DS":
        wf = ["ADIVaR", "AmpliconDS"]
    return wf

def getRunCmd( workflow, in_spl_folder, out_run_folder ):
    """
    @summary: Returns the command to launch the workflow.
    @param protocol: [dict] **************************************************************************************
    @param in_spl_folder: [str] Path to the sample folder (containing fastq and the samplesheet).
    @param out_run_folder: [str] Path to the workflow output folder.
    @return: [None/list] The command if the corresponding workflow exists and None otherwise.
    """
    cmd = None
    if workflow == "ADIVaR":
        cmd = getADIVaRCmd( in_spl_folder, out_run_folder, protocol["design"] )
    elif workflow == "AmpliconDS":
        cmd = getAmpliconDSCmd( in_spl_folder, out_run_folder, protocol["design"] )
    return cmd

def getAmpliconDSCmd( in_spl_folder, out_run_folder, design ):
    """
    @summary: Returns the command to launch the varainst annotation on MiSeq reporter outputs.
    @param in_spl_folder: [str] Path to the sample folder (containing fastq and the samplesheet).
    @param design: [str] Path to the folder containing the files describing the amplicons.
    @return: [list] The command.
    """
    cmd = [
        workflow_path.replace("WF_NAME", "AmpliconDSAnnot"), "amplicondsannot",
        "--RNA-selection", os.path.join(ressources_folder, design, "reference_RNA.tsv"),
        "--pos-ctrl-names", "HORIZON", "--pos-ctrl-names", "horizon", "--pos-ctrl-names", "Horizon",
        "--pos-ctrl-expected", os.path.join(ressources_folder, design, genome["assembly"] + "_chr", "pos_ctrl_expected.vcf"),
        "--assembly-version", genome["assembly"],
        "--filters", os.path.join(ressources_folder, "ampliDS_filters_wfAmpliconDS.json"),
        "--samplesheet", os.path.join(in_spl_folder, "SampleSheet.csv"),
        "--output-dir", out_run_folder
    ]
    return cmd

def getADIVaRCmd( in_spl_folder, out_run_folder, design ):
    """
    @summary: Returns the command to launch the amplicon double strand workflow.
    @param in_spl_folder: [str] Path to the sample folder (containing fastq and the samplesheet).
    @param out_run_folder: [str] Path to the workflow output folder.
    @param design: [str] Path to the folder containing the files describing the amplicons.
    @return: [list] The command.
    """
    cmd = [
        workflow_path.replace("WF_NAME", "ADIVaR"), "adivar",
        "--R1-end-adapter", os.path.join(ressources_folder, "adapters", "Illumina_3prim_adapter.fasta"),
        "--R2-end-adapter", os.path.join(ressources_folder, "adapters", "Illumina_5prim_adapter_rvc.fasta"),
        "--libA-folder", os.path.join(ressources_folder, design, genome["assembly"], "libA"),
        "--libB-folder", os.path.join(ressources_folder, design, genome["assembly"], "libB"),
        "--RNA-selection", os.path.join(ressources_folder, design, "reference_RNA.tsv"),
        "--pos-ctrl-names", "HORIZON", "--pos-ctrl-names", "horizon", "--pos-ctrl-names", "Horizon",
        "--pos-ctrl-expected", os.path.join(ressources_folder, design, genome["assembly"], "pos_ctrl_expected.vcf"),
        "--assembly-version", genome["assembly"],
        "--genome-seq", genome["sequences"],
        "--filters", os.path.join(ressources_folder, "ampliDS_filters.json"),
        "--samplesheet", os.path.join(in_spl_folder, "SampleSheet.csv"),
        "--output-dir", out_run_folder
    ]
    return cmd


########################################################################
#
# MAIN
#
########################################################################
if __name__ == "__main__":
    # Manage parameters
    parser = argparse.ArgumentParser( description="This script uses an infinite loop to listen the Illumina's sequencer output folder and launch the appropriate workflow when a run is ended." )
    parser.add_argument( '-r', '--roll-time', type=int, default=(60*20), help="The time between each sequencer output folder evaluation (in seconds). [Default: %(default)s]"  )
    parser.add_argument( '-v', '--version', action='version', version=__version__ )
    group_input = parser.add_argument_group( 'Inputs' ) # Inputs
    group_input.add_argument( '-l', '--listened-folder', required=True, help="The sequencer output folder." )
    group_output = parser.add_argument_group( 'Outputs' ) # Outputs
    group_output.add_argument( '-s', '--storage-folder', required=True, help='Path to the storage folder. The run folder will be moved to this folder after process.')
    group_output.add_argument( '-a', '--analysis-folder', required=True, help='Path to the workflows output folder ********************.')
    args = parser.parse_args()

    # Process
    while True:
        for filename in os.listdir( args.listened_folder ):
            in_run_folder = os.path.join( args.listened_folder, filename )
            if os.path.isdir(in_run_folder):
                out_run_folder = os.path.join( args.analysis_folder, filename )
                if os.path.exists(os.path.join(in_run_folder, "CompletedJobInfo.xml")): # The run is ended
                    if not os.path.exists(out_run_folder):
                        os.mkdir( out_run_folder )
                    in_spl_folder = os.path.join( in_run_folder, "Data", "Intensities", "BaseCalls" )
                    protocol = getProtocol( in_spl_folder )
                    # Analysis workflows
                    for curr_wf in getWorkflows(protocol):
                        out_wf_folder = os.path.join( out_run_folder, curr_wf )
                        if os.path.exists(out_wf_folder):
                            warnings.warn( 'The workflow "{}" cannot be run for run "{}".'.format(curr_wf, in_run_folder) )
                        else:
                            os.mkdir( out_wf_folder )
                            cmd_analysis = getRunCmd( curr_wf, in_spl_folder, out_wf_folder )
                            with open(os.path.join(out_wf_folder, "log.txt"), "w") as FH_log:
                                FH_log.write( "[START]\t" + datetime.datetime.now().isoformat() + "\n" )
                                FH_log.write( "[CMD]\t" + " ".join(cmd_analysis) + "\n" )
                            exec_cmd( cmd_analysis )
                            with open(os.path.join(out_wf_folder, "log.txt"), "a") as FH_log:
                                FH_log.write( "[END]\t" + datetime.datetime.now().isoformat() + "\n" )
                    # Move Illumina analysis
                    if protocol["workflow"] == "Amplicon - DS":
                        illumina_analysis_folder = os.path.join( in_spl_folder, "Alignment" )
                        cmd_copy_analysis = ["rsync", "--recursive", "--perms", "--times", illumina_analysis_folder + os.sep, os.path.join(out_run_folder, "AmpliconDS")]
                        exec_cmd( cmd_copy_analysis )
                        cmd_rm_analysis = ["rm", "-r", illumina_analysis_folder]
                        exec_cmd( cmd_rm_analysis )
                    # Copy raw data
                    cmd_copy_raw = ["rsync", "--recursive", "--perms", "--times", in_run_folder + os.sep, os.path.join(args.storage_folder, filename)]
                    exec_cmd( cmd_copy_raw )
                    cmd_rm_analysis = ["rm", "-r", in_run_folder]
                    exec_cmd( cmd_rm_analysis )
        time.sleep( args.roll_time )
