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
__version__ = '1.0.0'
__email__ = 'escudie.frederic@iuct-oncopole.fr'
__status__ = 'prod'

import os
import sys
import pysam
import argparse



########################################################################
#
# FUNCTIONS
#
########################################################################
def getSelectedAreas( input_panel ):
    """
    @summary: Returns the list of selected areas from a BED file.
    @param input_panel: [str] The path to the amplicons with their primers (format: BED)
    @return: [list] The list of BED's areas. Each area is represented by a dictionary with this format: {"region":"chr1", "start":501, "end":608, "strand":"+", "id":"gene_98"}.
    """
    selected_areas = list()
    with open(input_panel) as FH_panel:
        for line in FH_panel:
            if not line.startswith("browser ") and not line.startswith("track ") and not line.startswith("#"):
                fields = [elt.strip() for elt in line.split("\t")]
                selected_areas.append({
                    "region": fields[0],
                    "start": int(fields[1]) +1, # Start in BED is 0-based
                    "end": int(fields[2]),
                    "id": fields[3],
                    "strand": fields[5]
                })
    return( selected_areas )

def getSelectedAreasByChr( input_panel ):
    """
    @summary: Returns by chromosome the list of selected areas from a BED file.
    @param input_panel: [str] The path to the amplicons with their primers (format: BED)
    @return: [dict] By chromosome the list of BED's areas. Each area is represented by a dictionary with this format: {"region":"chr1", "start":501, "end":608, "strand":"+", "id":"gene_98"}.
    """
    selected_areas = getSelectedAreas( input_panel )
    selected_areas = sorted(selected_areas, key=lambda x: (x["region"], x["start"], x["end"]))
    
    area_by_chr = dict()
    for curr_area in selected_areas:
        chrom = curr_area["region"]
        if chrom not in area_by_chr:
            area_by_chr[chrom] = list()
        area_by_chr[chrom].append( curr_area )
    
    return( area_by_chr )

def getSourceRegion( read, regions, anchor_offset=0 ):
    """
    @summary: Returns the region where the read come from. Returns None if no region corresponds to the read.
    @param read: [pysam.AlignedSegment] The evaluated read.
    @param regions: [list] Evaluated source regions. Each area must be represented by a dictionary with the following format: {"region":"chr1", "start":501, "end":608, "strand":"+", "id":"gene_98"}.
    @param anchor_offset: [int] The alignment of the read can start at N nucleotids after the start of the primer. This parameter allows to take account the possible mismatches on the firsts read positions.
    @return: [None/dict] The region where the read come from.
    """
    overlapped_region = None
    ref_start = read.reference_start + 1
    ref_end = read.reference_end
    if read.is_reverse:
        for curr_region in regions:
            if ref_end < curr_region["start"]:
                break
            if ref_end <= curr_region["end"]:
                if ref_end >= curr_region["end"] - anchor_offset:
                    overlapped_region = curr_region
                    break
    else:
        for curr_region in regions:
            if ref_start < curr_region["start"]:
                break
            if ref_start >= curr_region["start"]:
                if ref_start <= curr_region["start"] + anchor_offset:
                    overlapped_region = curr_region
                    break
    return( overlapped_region )

def hasValidStrand( read, ampl_region ):
    """
    @summary: Returns True if the read is stranded like if it comes from the specified region.
    @param read: [pysam.AlignedSegment] The evaluated read.
    @param ampl_region: [dict] The amplicon region. The key "strand" must refer one of the following value: "+" or "-".
    @return: [bool] True if the read is stranded like if it comes from the specified region.
    """
    has_valid_strand = False
    if read.is_read1:
        if read.is_reverse:
            if ampl_region["strand"] == "-":
                has_valid_strand = True                    
        else:
            if ampl_region["strand"] == "+":
                has_valid_strand = True
    else:
        if read.is_reverse:
            if ampl_region["strand"] == "+":
                has_valid_strand = True                    
        else:
            if ampl_region["strand"] == "-":
                has_valid_strand = True
    return( has_valid_strand )


########################################################################
#
# MAIN
#
########################################################################
if __name__ == "__main__":
    # Manage parameters
    parser = argparse.ArgumentParser( description='Adds RG corresponding to the panel amplicon. for a reads pair the amplicon is determined from the position of the first match position of the reads (primers start positions).' )
    parser.add_argument( '-v', '--version', action='version', version=__version__ )
    parser.add_argument( '-t', '--RG-tag', default='LB', help='RG tag used to store the area ID. [Default: %(default)s]' )
    parser.add_argument( '-l', '--anchor-offset', type=int, default=4, help='The alignment of the read can start at N nucleotids after the start of the primer. This parameter allows to take account the possible mismatches on the firsts read positions. [Default: %(default)s]' )
    group_input = parser.add_argument_group( 'Inputs' ) # Inputs
    group_input.add_argument( '-a', '--input-aln', required=True, help='The path to the alignments files (format: BAM). This file must be sorted by coordinates.' )
    group_input.add_argument( '-p', '--input-panel', required=True, help='Path to the list of amplicons with their primers (format: BED). Each area must have an unique ID in the name field and a strand.' )
    group_output = parser.add_argument_group( 'Outputs' ) # Outputs
    group_output.add_argument( '-o', '--output-aln', required=True, help='The path to the alignments file (format: BAM).' )
    args = parser.parse_args()

    # Count
    total_reads = 0.0
    unpaired_reads = 0
    unmapped_pairs = 0
    out_target_reads = 0
    reverse_reads = 0
    valid_reads = 0
    valid_reads_valid_pair = 0
    
    # Get panel regions
    panel_regions = getSelectedAreasByChr( args.input_panel )
    
    # Filter reads in panel
    RG_id_by_source = dict()
    tmp_aln = args.output_aln + "_tmp.bam"
    valid_reads_by_id = dict()
    with pysam.AlignmentFile( args.input_aln, "rb" ) as FH_in:
        # Replace RG in header
        new_header = FH_in.header.copy()
        new_header["RG"] = list()
        RG_idx = 1
        for chrom in panel_regions:
            for curr_area in panel_regions[chrom]:
                new_header["RG"].append({"ID": str(RG_idx), args.RG_tag: curr_area["id"]})
                RG_id_by_source[curr_area["id"]] = str(RG_idx)
                RG_idx += 1
        # Parse reads
        with pysam.AlignmentFile( tmp_aln, "wb", header=new_header ) as FH_out:
            for curr_read in FH_in.fetch(until_eof=True):
                if not curr_read.is_secondary:
                    total_reads += 1
                    if not curr_read.is_paired:
                        unpaired_reads += 1
                    elif curr_read.is_unmapped or curr_read.mate_is_unmapped:
                        unmapped_pairs += 1
                    else:
                        source_region = None
                        if curr_read.reference_name in panel_regions:
                            source_region = getSourceRegion( curr_read, panel_regions[curr_read.reference_name], args.anchor_offset )
                        if source_region is None:
                            out_target_reads += 1
                        elif not hasValidStrand( curr_read, source_region ):
                            reverse_reads += 1
                        else:
                            valid_reads += 1
                            curr_read.set_tag( "RG", RG_id_by_source[source_region["id"]] )
                            if curr_read.query_name in valid_reads_by_id: # Pair is valid
                                prev_read = valid_reads_by_id[curr_read.query_name]
                                if prev_read is not None:
                                    valid_reads_valid_pair += 2
                                    FH_out.write( prev_read )
                                    valid_reads_by_id[curr_read.query_name] = None
                                FH_out.write( curr_read )
                            else:
                                valid_reads_by_id[curr_read.query_name] = curr_read
    
    # Sort output file
    pysam.sort( "-o", args.output_aln, tmp_aln )
    os.remove( tmp_aln )

    # Display stat
    print(
        "Category\tCount\tRatio",
        "Unpaired\t{}\t{:5f}".format( unpaired_reads, unpaired_reads/total_reads ),
        "Unmapped\t{}\t{:5f}".format( unmapped_pairs, unmapped_pairs/total_reads ),
        "Out_target\t{}\t{:5f}".format( out_target_reads, out_target_reads/total_reads ),
        "Cross_panel\t{}\t{:5f}".format( reverse_reads, reverse_reads/total_reads ),
        "Valid\t{}\t{:5f}".format( valid_reads_valid_pair, valid_reads_valid_pair/total_reads ),
        sep="\n"
    )