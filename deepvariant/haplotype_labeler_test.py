# Copyright 2017 Google Inc.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Tests for deepvariant.haplotype_labeler."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import itertools

from absl.testing import absltest
from absl.testing import parameterized
from deepvariant.util.genomics import variants_pb2

from deepvariant import haplotype_labeler


def _test_variant(start, alleles, gt=None):
  variant = variants_pb2.Variant(
      reference_name='20',
      start=start,
      end=start + len(alleles[0]),
      reference_bases=alleles[0],
      alternate_bases=alleles[1:],
  )

  if gt:
    variant.calls.add(genotype=gt)

  return variant


class LabelerMatchTests(parameterized.TestCase):

  def setUp(self):
    self.haplotypes = ['AC', 'GT']
    self.variants = [
        _test_variant(42, ['A', 'G']),
        _test_variant(43, ['G', 'A']),
        _test_variant(44, ['C', 'T']),
    ]
    self.truth_variants = [
        _test_variant(42, ['A', 'G'], [0, 1]),
        _test_variant(44, ['C', 'T'], [0, 1]),
        _test_variant(45, ['G', 'A'], [1, 1]),
    ]
    self.matched_variant_genotypes = [(0, 1), (0, 0), (0, 1)]
    self.matched_truth_genotypes = [(0, 1), (0, 1), (0, 0)]
    self.match = haplotype_labeler.LabelerMatch(
        self.haplotypes, self.variants, self.matched_variant_genotypes,
        self.truth_variants, self.matched_truth_genotypes)

  def test_fields_are_expected(self):
    self.assertEqual(self.match.haplotypes, self.haplotypes)
    self.assertEqual(self.match.variants, self.variants)
    self.assertEqual(self.match.truth_variants, self.truth_variants)
    self.assertEqual(self.match.matched_variant_genotypes,
                     self.matched_variant_genotypes)
    self.assertEqual(self.match.matched_truth_genotypes,
                     self.matched_truth_genotypes)

    # Computed fields.
    self.assertEqual(self.match.truth_genotypes,
                     haplotype_labeler.variant_genotypes(self.truth_variants))
    self.assertEqual(self.match.n_false_positives, 1)
    self.assertEqual(self.match.n_false_negatives, 2)
    self.assertEqual(self.match.n_true_positives, 2)
    self.assertEqual(self.match.match_quality, (2, 1, 2))

  def test_str(self):
    self.assertIn('LabelerMatch(', str(self.match))

  def test_variants_with_assigned_genotypes(self):
    self.assertEqual(self.match.variants_with_assigned_genotypes(), [
        _test_variant(42, ['A', 'G'], [0, 1]),
        _test_variant(43, ['G', 'A'], [0, 0]),
        _test_variant(44, ['C', 'T'], [0, 1]),
    ])
    # Assert that we have no genotypes in self.variants to check that
    # variants_with_assigned_genotypes isn't modifying our variants.
    for v in self.match.variants:
      self.assertFalse(v.calls, 'Variant genotypes modified')

  @parameterized.parameters(
      # All genotypes match, so we have no FNs and no FPs.
      dict(
          vgenotypes=[(0, 1), (0, 1)],
          matched_tgenotypes=[(0, 1), (0, 1)],
          tgenotypes=[(0, 1), (0, 1)],
          expected_fns=0,
          expected_fps=0,
          expected_tps=2,
      ),
      #
      # Here are a few cases where we false negatives.
      #
      dict(
          vgenotypes=[(0, 1), (0, 1)],
          # True het is 0, 0 in second true variant.
          matched_tgenotypes=[(0, 1), (0, 0)],
          tgenotypes=[(0, 1), (0, 1)],
          expected_fns=1,
          expected_fps=0,
          expected_tps=2,
      ),
      dict(
          vgenotypes=[(0, 1), (0, 1)],
          # True hom-alt is het in second true variant.
          matched_tgenotypes=[(0, 1), (0, 1)],
          tgenotypes=[(0, 1), (1, 1)],
          expected_fns=1,
          expected_fps=0,
          expected_tps=2,
      ),
      dict(
          vgenotypes=[(0, 1), (0, 1)],
          # True hom-alts are het in first and second true variants.
          matched_tgenotypes=[(0, 1), (0, 1)],
          tgenotypes=[(1, 1), (1, 1)],
          expected_fns=2,
          expected_fps=0,
          expected_tps=2,
      ),
      dict(
          vgenotypes=[(0, 1), (0, 1)],
          # True hom-alts are hom-ref in first and second true variants.
          matched_tgenotypes=[(0, 0), (0, 0)],
          tgenotypes=[(1, 1), (1, 1)],
          expected_fns=4,
          expected_fps=0,
          expected_tps=2,
      ),
      #
      # Here are a few cases where we false positives.
      #
      dict(
          # The first variant genotype is hom-ref so we have one FP.
          vgenotypes=[(0, 0), (0, 1)],
          matched_tgenotypes=[(0, 1), (0, 1)],
          tgenotypes=[(0, 1), (0, 1)],
          expected_fns=0,
          expected_fps=1,
          expected_tps=1,
      ),
      dict(
          # The second variant genotype is hom-ref so we have one FP.
          vgenotypes=[(0, 1), (0, 0)],
          matched_tgenotypes=[(0, 1), (0, 1)],
          tgenotypes=[(0, 1), (0, 1)],
          expected_fns=0,
          expected_fps=1,
          expected_tps=1,
      ),
      dict(
          # Both variant genotypes are hom-ref, so we have two FPs.
          vgenotypes=[(0, 0), (0, 0)],
          matched_tgenotypes=[(0, 1), (0, 1)],
          tgenotypes=[(0, 1), (0, 1)],
          expected_fns=0,
          expected_fps=2,
          expected_tps=0,
      ),
  )
  def test_fns_fps(self, vgenotypes, matched_tgenotypes, tgenotypes,
                   expected_fns, expected_fps, expected_tps):
    match = haplotype_labeler.LabelerMatch(
        haplotypes=self.haplotypes,
        variants=[
            _test_variant(42, ['A', 'G']),
            _test_variant(43, ['G', 'A']),
        ],
        matched_variant_genotypes=vgenotypes,
        truth_variants=[
            _test_variant(42, ['A', 'G'], tgenotypes[0]),
            _test_variant(43, ['G', 'A'], tgenotypes[1]),
        ],
        matched_truth_genotypes=matched_tgenotypes)
    self.assertEqual(match.n_false_negatives, expected_fns)
    self.assertEqual(match.n_false_positives, expected_fps)
    self.assertEqual(match.n_true_positives, expected_tps)
    self.assertEqual(match.n_true_positives + match.n_false_positives, 2)
    self.assertEqual(match.match_quality,
                     (expected_fns, expected_fps, expected_tps))


class LabelExamplesTest(parameterized.TestCase):
  # Many of these tests are cases from our labeler analysis doc:
  # https://docs.google.com/document/d/1V89IIT0YM3P0gH_tQb-ahodf8Jvnz0alXEnjCf6JVNo

  def assertGetsCorrectLabels(self,
                              candidates,
                              true_variants,
                              ref,
                              expected_genotypes,
                              start=None,
                              end=None):
    start = start or ref.start
    end = end or ref.end
    labeled_variants = haplotype_labeler.label_variants(candidates,
                                                        true_variants, ref)
    self.assertIsNotNone(labeled_variants)

    # Check that the genotypes of our labeled variants are the ones we expect.
    self.assertEqual(
        haplotype_labeler.variant_genotypes(labeled_variants),
        [tuple(x) for x in expected_genotypes])

  @parameterized.parameters(
      dict(genotype=[0, 0], expected={(0, 0)}),
      dict(genotype=[0, 1], expected={(0, 0), (0, 1)}),
      dict(genotype=[1, 1], expected={(0, 0), (0, 1), (1, 1)}),
      dict(genotype=[0, 2], expected={(0, 0), (0, 2)}),
      dict(genotype=[2, 2], expected={(0, 0), (0, 2), (2, 2)}),
      dict(genotype=[1, 2], expected={(0, 0), (0, 2), (0, 1), (1, 2)}),
  )
  def test_with_false_negative_genotypes(self, genotype, expected):
    self.assertEqual(
        haplotype_labeler.with_false_negative_genotypes(genotype), expected)

  @parameterized.parameters(
      # All possible genotypes for a simple tri-allelic case.
      (dict(
          variants=[
              _test_variant(11, ['TG', 'A', 'TGC'], gt),
          ],
          ref=haplotype_labeler.Reference('TG', 11),
          expected_frags=expected,
          expected_next_pos=13) for gt, expected in {
              # Simple bi-allelic configurations:
              (0, 0): {(0,): 'TG'},
              (0, 1): {(0,): 'TG', (1,): 'A'},
              (1, 0): {(0,): 'TG', (1,): 'A'},
              (1, 1): {(1,): 'A'},
              # Multi-allelic configurations:
              (0, 2): {(0,): 'TG', (2,): 'TGC'},
              (1, 2): {(1,): 'A', (2,): 'TGC'},
              (2, 2): {(2,): 'TGC'},
          }.iteritems()),
  )
  def test_build_all_haplotypes_single_variant(
      self, variants, ref, expected_frags, expected_next_pos):
    variants_and_genotypes = [
        haplotype_labeler.VariantAndGenotypes(v, tuple(v.calls[0].genotype))
        for v in variants
    ]
    frags, next_pos = haplotype_labeler.build_all_haplotypes(
        variants_and_genotypes, ref.start, ref)
    self.assertEqual(frags, expected_frags)
    self.assertEqual(next_pos, expected_next_pos)

  @parameterized.parameters(
      ('G', 'A'),
      ('GG', 'A'),
      ('GGG', 'A'),
      ('GGGG', 'A'),
      ('A', 'G'),
      ('A', 'GG'),
      ('A', 'GGG'),
      ('A', 'GGGG'),
  )
  def test_build_all_haplotypes_next_pos_is_correct(self, ref, alt):
    # Check that the next_pos calculation is working.
    pos = 10
    for gt in [(0, 0), (0, 1), (1, 1)]:
      _, next_pos = haplotype_labeler.build_all_haplotypes(
          [
              haplotype_labeler.VariantAndGenotypes(
                  _test_variant(pos, [ref, alt]), gt)
          ],
          last_pos=pos,
          ref=haplotype_labeler.Reference(ref, pos))
      self.assertEqual(next_pos, pos + len(ref))

  @parameterized.parameters(
      # A single deletion overlapping a SNP:
      # ref: xTG
      # v1:   A-
      # v2:    C
      dict(
          variants=[
              _test_variant(11, ['TG', 'A'], (0, 1)),
              _test_variant(12, ['G', 'C'], (0, 1)),
          ],
          ref=haplotype_labeler.Reference('xTG', 10),
          expected_frags={
              (0, 0): 'xTG',    # haplotype 0|0.
              (0, 1): 'xTC',    # haplotype 0|1.
              (1, 0): 'xA',     # haplotype 1|0.
              (1, 1): None,     # haplotype 1|1 => invalid.
          },
          expected_next_pos=13),
      # Deletion overlapping two downstream events (SNP and insertion):
      # ref: xTGC
      # v1:   A--
      # v2:    C
      # v3:     TTT
      dict(
          variants=[
              _test_variant(11, ['TGC', 'A'], (0, 1)),
              _test_variant(12, ['G', 'C'], (0, 1)),
              _test_variant(13, ['C', 'TTT'], (0, 1)),
          ],
          ref=haplotype_labeler.Reference('xTGC', 10),
          expected_frags={
              (0, 0, 0): 'xTGC',    # haplotype 0|0|0.
              (0, 0, 1): 'xTGTTT',  # haplotype 0|0|1.
              (0, 1, 0): 'xTCC',    # haplotype 0|1|0.
              (0, 1, 1): 'xTCTTT',  # haplotype 0|1|1.
              (1, 0, 0): 'xA',      # haplotype 1|0|0.
              (1, 0, 1): None,      # haplotype 1|0|1 => invalid.
              (1, 1, 0): None,      # haplotype 1|1|0 => invalid.
              (1, 1, 1): None,      # haplotype 1|1|1 => invalid.
          },
          expected_next_pos=14),
      # Two incompatible deletions to check that the end extension is working:
      # pos: 01234
      # ref: xTGCA
      # v1:   T-
      # v2:    G-
      dict(
          variants=[
              _test_variant(11, ['TG', 'T'], (0, 1)),
              _test_variant(12, ['GC', 'G'], (0, 1)),
          ],
          ref=haplotype_labeler.Reference('xTGCA', 10),
          expected_frags={
              (0, 0): 'xTGC',   # haplotype 0|0.
              (0, 1): 'xTG',    # haplotype 0|1.
              (1, 0): 'xTC',    # haplotype 1|0.
              (1, 1): None,     # haplotype 1|1 => invalid.
          },
          expected_next_pos=14),
      # Multiple overlapping deletions with complex incompatibilities:
      # ref: xTGCGA
      # v1:   A--
      # v2:    G---  [conflicts with v1]
      # v3:     C-   [conflicts with v1 and v2]
      # v4:      G-  [conflicts with v2 and v3, ok with v1]
      # v5:       C  [conflicts with v2 and v4, ok with v1, v3]
      dict(
          variants=[
              _test_variant(11, ['TGC', 'A'], (0, 1)),
              _test_variant(12, ['GCGA', 'G'], (0, 1)),
              _test_variant(13, ['CG', 'C'], (0, 1)),
              _test_variant(14, ['GA', 'G'], (0, 1)),
              _test_variant(15, ['A', 'C'], (0, 1)),
          ],
          ref=haplotype_labeler.Reference('xTGCGA', 10),
          expected_frags={
              (0, 0, 0, 0, 0): 'xTGCGA',    # haplotype 0|0|0|0|0.
              (0, 0, 0, 0, 1): 'xTGCGC',    # haplotype 0|0|0|0|1.
              (0, 0, 0, 1, 0): 'xTGCG',     # haplotype 0|0|0|1|0.
              (0, 0, 0, 1, 1): None,        # haplotype 0|0|0|1|1.
              (0, 0, 1, 0, 0): 'xTGCA',     # haplotype 0|0|1|0|0.
              (0, 0, 1, 0, 1): 'xTGCC',     # haplotype 0|0|1|0|1.
              (0, 0, 1, 1, 0): None,        # haplotype 0|0|1|1|0.
              (0, 0, 1, 1, 1): None,        # haplotype 0|0|1|1|1.
              (0, 1, 0, 0, 0): 'xTG',       # haplotype 0|1|0|0|0.
              (0, 1, 0, 0, 1): None,        # haplotype 0|1|0|0|1.
              (0, 1, 0, 1, 0): None,        # haplotype 0|1|0|1|0.
              (0, 1, 0, 1, 1): None,        # haplotype 0|1|0|1|1.
              (0, 1, 1, 0, 0): None,        # haplotype 0|1|1|0|0.
              (0, 1, 1, 0, 1): None,        # haplotype 0|1|1|0|1.
              (0, 1, 1, 1, 0): None,        # haplotype 0|1|1|1|0.
              (0, 1, 1, 1, 1): None,        # haplotype 0|1|1|1|1.
              (1, 0, 0, 0, 0): 'xAGA',      # haplotype 1|0|0|0|0.
              (1, 0, 0, 0, 1): 'xAGC',      # haplotype 1|0|0|0|1.
              (1, 0, 0, 1, 0): 'xAG',       # haplotype 1|0|0|1|0.
              (1, 0, 0, 1, 1): None,        # haplotype 1|0|0|1|1.
              (1, 0, 1, 0, 0): None,        # haplotype 1|0|1|0|0.
              (1, 0, 1, 0, 1): None,        # haplotype 1|0|1|0|1.
              (1, 0, 1, 1, 0): None,        # haplotype 1|0|1|1|0.
              (1, 0, 1, 1, 1): None,        # haplotype 1|0|1|1|1.
              (1, 1, 0, 0, 0): None,        # haplotype 1|1|0|0|0.
              (1, 1, 0, 0, 1): None,        # haplotype 1|1|0|0|1.
              (1, 1, 0, 1, 0): None,        # haplotype 1|1|0|1|0.
              (1, 1, 0, 1, 1): None,        # haplotype 1|1|0|1|1.
              (1, 1, 1, 0, 0): None,        # haplotype 1|1|1|0|0.
              (1, 1, 1, 0, 1): None,        # haplotype 1|1|1|0|1.
              (1, 1, 1, 1, 0): None,        # haplotype 1|1|1|1|0.
              (1, 1, 1, 1, 1): None,        # haplotype 1|1|1|1|1.
          },
          expected_next_pos=16),
  )
  def test_build_all_haplotypes_overlapping(
      self, variants, ref, expected_frags, expected_next_pos):
    # redacted
    variants_and_genotypes = [
        haplotype_labeler.VariantAndGenotypes(v, tuple(v.calls[0].genotype))
        for v in variants
    ]
    frags, next_pos = haplotype_labeler.build_all_haplotypes(
        variants_and_genotypes, ref.start, ref)
    self.assertEqual(
        frags, {k: v
                for k, v in expected_frags.iteritems()
                if v is not None})
    self.assertEqual(next_pos, expected_next_pos)

  @parameterized.parameters(
      # Check that simple bi-allelic matching works for all possible possible
      # genotypes and a variety of types of alleles.
      (dict(
          candidate_alleles=alleles,
          truth_alleles=alleles,
          truth_genotype=gt,
          # Returns [0, 1] even if truth is [1, 0], so sort the genotypes for
          # the expected value.
          expected_genotype=sorted(gt),
      )
       for gt in [[0, 1], [1, 0], [1, 1]]
       for alleles in [['A', 'C'], ['ACC', 'A'], ['A', 'ATG'], ['AC', 'GT']]),
  )
  def test_single_variants(self, candidate_alleles, truth_alleles,
                           truth_genotype, expected_genotype):
    candidate = _test_variant(42, candidate_alleles)
    truth = _test_variant(42, truth_alleles, truth_genotype)
    ref_allele = sorted([candidate_alleles[0], truth_alleles[0]], key=len)[0]
    self.assertGetsCorrectLabels(
        candidates=[candidate],
        true_variants=[truth],
        ref=haplotype_labeler.Reference('x' + ref_allele + 'y', 41),
        expected_genotypes=[expected_genotype])

  @parameterized.parameters(
      dict(
          candidate_alleles=['A', 'C'],
          truth_alleles=['A', 'G', 'C'],
          truth_genotypes_and_expected={
              (0, 2): (0, 1),  # A/C => 0/C
              (1, 2): (0, 1),  # G/C => 0/C
              (1, 1): (0, 0),  # G/G => 0/0
              (2, 2): (1, 1),  # C/C => C/C
          }
      ),
      dict(
          candidate_alleles=['A', 'C'],
          truth_alleles=['A', 'C', 'G'],
          truth_genotypes_and_expected={
              (0, 1): (0, 1),  # A/C => 0/C
              (2, 1): (0, 1),  # G/C => 0/C
              (2, 2): (0, 0),  # G/G => 0/0
              (1, 1): (1, 1),  # C/C => C/C
          },
      ),
      dict(
          candidate_alleles=['A', 'TT', 'TTT'],
          truth_alleles=['A', 'C', 'G'],
          truth_genotypes_and_expected={
              (i, j): (0, 0) for i, j in itertools.combinations([0, 1, 2], 2)
          }
      ),
      # Here the candidate is also multi-allelic
      dict(
          candidate_alleles=['A', 'G', 'C'],
          truth_alleles=['A', 'C', 'G'],
          truth_genotypes_and_expected={
              (0, 1): (0, 2),
              (0, 2): (0, 1),
              (1, 1): (2, 2),
              (1, 2): (1, 2),
              (2, 2): (1, 1),
          },
      ),
  )
  def test_multi_allelic(self, candidate_alleles, truth_alleles,
                         truth_genotypes_and_expected):
    candidate = _test_variant(42, candidate_alleles)
    for true_gt, expected_gt in truth_genotypes_and_expected.iteritems():
      truth = _test_variant(42, truth_alleles, true_gt)
      ref_allele = sorted([candidate_alleles[0], truth_alleles[0]], key=len)[0]
      self.assertGetsCorrectLabels(
          candidates=[candidate],
          true_variants=[truth],
          ref=haplotype_labeler.Reference('x' + ref_allele + 'y', 41),
          expected_genotypes=[expected_gt])

  def test_false_variants_get_homref_genotype(self):
    ref = haplotype_labeler.Reference('xACGTAy', 10)
    v1 = _test_variant(11, ['A', 'T'], [0, 1])
    v2 = _test_variant(13, ['G', 'GG'], [1, 1])
    all_fps = [
        _test_variant(12, ['C', 'G'], [0, 0]),
        _test_variant(14, ['T', 'A'], [0, 0]),
        _test_variant(15, ['A', 'AA'], [0, 0]),
    ]
    for n_fps in range(1, len(all_fps) + 1):
      for fps in itertools.combinations(all_fps, n_fps):
        candidates = haplotype_labeler.sort_variants([v1, v2] + list(fps))
        self.assertGetsCorrectLabels(
            candidates=candidates,
            true_variants=[v1, v2],
            ref=ref,
            expected_genotypes=haplotype_labeler.variant_genotypes(candidates))

  def test_false_negatives(self):
    ref = haplotype_labeler.Reference('xACGTAy', 10)
    v1 = _test_variant(11, ['A', 'T'], [0, 1])
    v2 = _test_variant(13, ['G', 'GG'], [1, 1])
    all_fns = [
        _test_variant(12, ['C', 'G'], [0, 1]),
        _test_variant(14, ['T', 'A', 'G'], [1, 2]),
        _test_variant(15, ['A', 'AA'], [1, 1]),
    ]
    for n_fns in [1]:
      # for n_fns in range(1, len(all_fns) + 1):
      for fns in itertools.combinations(all_fns, n_fns):
        candidates = [v1, v2]
        self.assertGetsCorrectLabels(
            candidates=candidates,
            true_variants=haplotype_labeler.sort_variants([v1, v2] + list(fns)),
            ref=ref,
            expected_genotypes=haplotype_labeler.variant_genotypes(candidates))

  # example 20:3528533 and 20:3528534
  def test_example1(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(3528531, ['ATAG', 'A']),
            _test_variant(3528537, ['A', 'ATT']),
        ],
        true_variants=[
            _test_variant(3528533, ['A', 'T'], [1, 1]),
            _test_variant(3528534, ['G', 'A'], [1, 1]),
            _test_variant(3528536, ['TA', 'T'], [1, 1]),
        ],
        ref=haplotype_labeler.Reference('xATAGTTATC', 3528530),
        expected_genotypes=[
            [1, 1],
            [1, 1],
        ])

  # example 20:4030071
  def test_example2(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(4030067, ['TC', 'T']),
            _test_variant(4030072, ['C', 'G']),
        ],
        true_variants=[
            _test_variant(4030071, ['CC', 'G'], [1, 1]),
        ],
        ref=haplotype_labeler.Reference('xTCCCCCA', 4030066),
        expected_genotypes=[
            [1, 1],
            [1, 1],
        ])

  # example 20:4568152
  def test_example3(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(4568151, ['AC', 'A']),
            _test_variant(4568154, ['TG', 'T']),
            _test_variant(4568156, ['G', 'T']),
            _test_variant(4568157, ['A', 'ATACCCTTT']),
        ],
        true_variants=[
            _test_variant(4568152, ['C', 'A'], [1, 1]),
            _test_variant(4568153, ['A', 'T'], [1, 1]),
            _test_variant(4568155, ['G', 'A'], [1, 1]),
            _test_variant(4568156, ['G', 'T'], [1, 1]),
            _test_variant(4568157, ['A', 'ACCCTTT'], [1, 1]),
        ],
        ref=haplotype_labeler.Reference('xACATGGATGGA', 4568150),
        expected_genotypes=[
            [1, 1],
            [1, 1],
            [1, 1],
            [1, 1],
        ])

  # example 20:1689636, 20:1689639, 20:1689640, 20:1689641
  def test_example4(self):
    # CTGTAAACAGAA [phased alts] + CGTGAATGAAA [phased ref]
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(1689633, ['C', 'CT']),
            _test_variant(1689635, ['TG', 'T']),
            _test_variant(1689638, ['ATG', 'A']),
            _test_variant(1689641, ['A', 'ACAG']),
        ],
        true_variants=[
            _test_variant(1689633, ['C', 'CT'], [1, 0]),
            _test_variant(1689636, ['G', 'A'], [1, 0]),
            _test_variant(1689639, ['T', 'C'], [1, 0]),
            _test_variant(1689640, ['G', 'A'], [1, 0]),
            _test_variant(1689641, ['A', 'G'], [1, 0]),
        ],
        ref=haplotype_labeler.Reference('xCGTGAATGAAA', 1689632),
        expected_genotypes=[
            [0, 1],
            [0, 1],
            [0, 1],
            [0, 1],
        ])

  # 20:2401511
  def test_example5(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(2401510, ['ATGT', 'A']),
            _test_variant(2401515, ['C', 'T']),
        ],
        true_variants=[
            _test_variant(2401511, ['TG', 'A'], [1, 1]),
            _test_variant(2401513, ['TAC', 'T'], [1, 1]),
        ],
        ref=haplotype_labeler.Reference('xATGTACACAG', 2401509),
        expected_genotypes=[
            [1, 1],
            [1, 1],
        ])

  # 20:2525695: genotype assign was incorrect in a previous run. This is because
  # the candidate variants overlap:
  #
  # ref: AAATT
  #  v1:  A--
  #  v2:   A-
  #
  # And this is causing us to construct incorrect haplotypes.
  def test_example6(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(2525696, ['AAT', 'A']),
            _test_variant(2525697, ['AT', 'T']),
        ],
        true_variants=[
            _test_variant(2525696, ['AAT', 'A'], [0, 1]),
        ],
        ref=haplotype_labeler.Reference('xAATT', 2525695),
        expected_genotypes=[
            [0, 1],
            [0, 0],
        ])

  # Variants were getting incorrect genotypes due to complex region.
  #
  # variants: candidates
  #   20:279768:G->C gt=(-1, -1)
  #   20:279773:ATA->C/CTA gt=(-1, -1)
  # variants: truth
  #   20:279773:A->C gt=(1, 0)
  #
  # pos    : 789012345678901
  # ref    : CGCCCCATACCTTTT
  # truth  :       C          => CGCCCCCTACCTTTT
  # DV 1   :  C               => CCCCCCATACCTTTT [bad]
  # DV 2.a :       C--        => CGCCCCCCTTTT    [bad]
  # DV 2.b :       CTA        => CGCCCCCTACCTTTT [match]
  #
  def test_example7(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(279768, ['G', 'C']),
            _test_variant(279773, ['ATA', 'C', 'CTA']),
        ],
        true_variants=[
            _test_variant(279773, ['A', 'C'], [0, 1]),
        ],
        ref=haplotype_labeler.Reference('CGCCCCATACCTTTT', 279767),
        expected_genotypes=[
            [0, 0],
            [0, 2],
        ])

  # redacted
  # that accepts a whole region of variants so we make sure it divides up the
  # problem into more fine-grained pieces that run quickly. The current call is
  # to a lower-level API that doesn't do variant chunking.
  # Commented out because this remains super slow.
  # def test_super_slow_example(self):
  #   self.assertGetsCorrectLabels(
  #       candidates=[
  #           _test_variant(32274452, ['C', 'G']),
  #           _test_variant(32274453, ['T', 'G']),
  #           _test_variant(32274456, ['A', 'G']),
  #           _test_variant(32274459, ['C', 'G']),
  #           _test_variant(32274461, ['T', 'G']),
  #           _test_variant(32274465, ['GACA', 'G']),
  #           _test_variant(32274467, ['CA', 'C']),
  #           _test_variant(32274470, ['C', 'G']),
  #           _test_variant(32274473, ['A', 'G']),
  #           _test_variant(32274474, ['AC', 'A']),
  #           _test_variant(32274475, ['C', 'A']),
  #           _test_variant(32274477, ['T', 'A']),
  #           _test_variant(32274480, ['G', 'C']),
  #       ],
  #       true_variants=[
  #           _test_variant(32274470, ['C', 'G'], (1, 1)),
  #       ],
  #       ref=haplotype_labeler.Reference(
  #           'GCTGGAGGCGTGGGGACACCGGAACATAGGCCCCGCCCCGCCCCGACGC', 32274451),
  #       expected_genotypes=[
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [1, 1],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #           [0, 0],
  #       ])

# Variants were getting incorrect genotypes in an exome callset.
#
# ref: AGACACACACACACAAAAAAAAATCATAAAATGAAG, start=214012389
# candidates 2:214012390:G->GAC
# candidates 2:214012402:CAA->C
# candidates 2:214012404:A->C
# true_variants 2:214012404:A->C
#
# 2:214012390:G->GAC => gt=(1, 1) new_label=2 old_label=0 alts=[0]
# 2:214012402:CAA->C => gt=(1, 1) new_label=2 old_label=0 alts=[0]
# 2:214012404:A->C => gt=(0, 0) new_label=0 old_label=2 alts=[0]
#
#           90--------- 0---------10--------20---
# pos    : 90  1234567890123456789012345678901234
# ref    : AG  ACACACACACACAAAAAAAAATCATAAAATGAAG
# truth  :                  C => AGACACACACACACACAAAAAAATCATAAAATGAAG
# DV 1   :  GAC               => [doesn't match]
# DV 2   :                C-- => [doesn't match]
# DV 1+2 : AGACACACACACACAC  AAAAAAATCATAAAATGAAG
# DV 1+2 :                    => AGACACACACACACACAAAAAAATCATAAAATGAAG [match]
# DV 3   :                  C => AGACACACACACACACAAAAAAATCATAAAATGAAG [match]
#
# So this is an interesting case. G->GAC + CAA->C matches the true haplotype,
# and the SNP itself gets assigned a FP status since we can have either two
# FPs (dv1 and dv2 candidates) or have just one (dv3). What's annoying here is
# that DV3 exactly matches the variant as described in the truth set. It's
# also strange that we've generated multiple equivalent potential variants
# here.
#
# This test ensures that we are picking the most parsimonous genotype
# assignment (e.g., fewest number of TPs) needed to explain the truth, after
# accounting for minimizing the number of FNs and FPs.
  def test_exome_variants_multiple_equivalent_representations(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(214012390, ['G', 'GAC']),
            _test_variant(214012402, ['CAA', 'C']),
            _test_variant(214012404, ['A', 'C']),
        ],
        true_variants=[
            _test_variant(214012404, ['A', 'C'], [1, 1]),
        ],
        ref=haplotype_labeler.Reference('AGACACACACACACAAAAAAAAATCAT',
                                        214012389),
        expected_genotypes=[
            [0, 1],
            [0, 1],
            [0, 1],
            # This configuration makes the most sense but we cannot choose it
            # if we want to minimize the number of FNs, FPs, and then TPs.
            # [0, 0],
            # [0, 0],
            # [1, 1],
        ])

  # Variant group: 5 candidates 2 truth variants
  # ref: Reference(bases=TGTTTTTTTTTAAAAAAATTATTTCTTCTTT, start=167012239)
  #   candidates 4:167012240:GT->G
  #   candidates 4:167012246:TTTT->A
  #   candidates 4:167012247:T->A
  #   candidates 4:167012248:T->A
  #   candidates 4:167012249:T->A
  #   true_variants 4:167012240:GTTT->G/GTT [2, 1]
  #   true_variants 4:167012249:T->A/TAA [2, 1]
  #   4:167012240:GT->G => gt=(1, 1) new_label=2 old_label=1 alts=[0]
  #   4:167012246:TTTT->A => gt=(0, 0) new_label=0 old_label=0 alts=[0]
  #   4:167012247:T->A => gt=(0, 0) new_label=0 old_label=0 alts=[0]
  #   4:167012248:T->A => gt=(0, 1) new_label=1 old_label=0 alts=[0]
  #   4:167012249:T->A => gt=(1, 1) new_label=2 old_label=1 alts=[0]
  def test_exome_complex_example(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(167012240, ['GT', 'G']),
            _test_variant(167012246, ['TTTT', 'A']),
            _test_variant(167012247, ['T', 'A']),
            _test_variant(167012248, ['T', 'A']),
            _test_variant(167012249, ['T', 'A']),
        ],
        true_variants=[
            _test_variant(167012240, ['GTTT', 'G', 'GTT'], [1, 2]),
            _test_variant(167012249, ['T', 'A', 'TAA'], [1, 2]),
        ],
        ref=haplotype_labeler.Reference('TGTTTTTTTTTAAAAAAATTATTTCTTCTTT',
                                        167012239),
        expected_genotypes=[
            [1, 1],
            [0, 0],
            [0, 0],
            [0, 1],
            [1, 1],
        ])

  # ref: GGGTGTGTGTGTGTGTGTGTGTGTGTGCGTGTGTGTGTTTGTGTTG, start=9508942
  #   candidates 20:9508943:GGT->G
  #   candidates 20:9508967:T->C/TGC
  #   candidates 20:9508967:T->C/TGC
  #   candidates 20:9508967:T->C/TGC
  #   true_variants 20:9508943:GGT->G [0, 1]
  #   true_variants 20:9508967:T->C/TGC [1, 2]
  #   20:9508943:GGT->G => gt=(0, 0) new_label=0 old_label=1 alts=[0
  #   20:9508967:T->C/TGC => gt=(1, 1) new_label=2 old_label=1 alts=[0]
  #   20:9508967:T->C/TGC => gt=(1, 1) new_label=0 old_label=1 alts=[1]
  #   20:9508967:T->C/TGC => gt=(1, 1) new_label=2 old_label=2 alts=[0, 1]
  #
  # This test fixes a bug where we weren't scoring our matches properly.
  # Previously we were not accounting for FPs in our score, so we were taking
  # a match with 0 FN, 1 FP, 1 TP over one with 0 FN, 0 FP, and 2 TP!
  #
  #      40------50--------60---------
  # pos: 2345678901234567890123456789012345678901234567
  # ref: GGGTGTGTGTGTGTGTGTGTGTGTGTGCGTGTGTGTGTTTGTGTTG
  # t1:   G--
  # t2a:                          C
  # t2b:                          Tgc
  #
  def test_bad_scoring_bug(self):
    self.assertGetsCorrectLabels(
        candidates=[
            _test_variant(9508943, ['GGT', 'G']),
            _test_variant(9508967, ['T', 'C', 'TGC']),
        ],
        true_variants=[
            _test_variant(9508943, ['GGT', 'G'], [0, 1]),
            _test_variant(9508967, ['T', 'C', 'TGC'], [1, 2]),
        ],
        ref=haplotype_labeler.Reference(
            'GGGTGTGTGTGTGTGTGTGTGTGTGTGCGTGTGTGTGTTTGTGTTG', 9508942),
        expected_genotypes=[
            [0, 1],
            [1, 2],
        ])


if __name__ == '__main__':
  absltest.main()