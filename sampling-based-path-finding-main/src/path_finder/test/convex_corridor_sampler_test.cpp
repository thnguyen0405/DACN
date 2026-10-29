#include "path_finder/sampler.h"

#include <gtest/gtest.h>

#include <string>
#include <vector>
#include <cmath>
#include <numeric>

namespace
{
  path_plan::ConvexRegion2D square(const std::string &id,
                                   double min_x,
                                   double min_y,
                                   double max_x,
                                   double max_y)
  {
    path_plan::ConvexRegion2D region;
    region.id = id;
    region.polygon = {
        Eigen::Vector2d(min_x, min_y),
        Eigen::Vector2d(max_x, min_y),
        Eigen::Vector2d(max_x, max_y),
        Eigen::Vector2d(min_x, max_y)};
    return region;
  }

  path_plan::ScoredConvexRegion2D scoredSquare(const std::string &id,
                                               double score,
                                               double min_x,
                                               double min_y,
                                               double max_x,
                                               double max_y)
  {
    path_plan::ScoredConvexRegion2D region;
    region.id = id;
    region.score = score;
    region.polygon = square(id, min_x, min_y, max_x, max_y).polygon;
    return region;
  }
}

TEST(ConvexCorridorGeometry, PointInsideBoundaryAndOutside)
{
  const auto polygon = square("A", 0.0, 0.0, 2.0, 2.0).polygon;
  EXPECT_TRUE(BiasSampler::pointInConvexPolygon(Eigen::Vector2d(1.0, 1.0), polygon));
  EXPECT_TRUE(BiasSampler::pointInConvexPolygon(Eigen::Vector2d(2.0, 1.0), polygon));
  EXPECT_FALSE(BiasSampler::pointInConvexPolygon(Eigen::Vector2d(3.0, 1.0), polygon));
}

TEST(ConvexCorridorGeometry, TriangleArea)
{
  EXPECT_DOUBLE_EQ(6.0, BiasSampler::triangleArea(
                            Eigen::Vector2d(0.0, 0.0),
                            Eigen::Vector2d(4.0, 0.0),
                            Eigen::Vector2d(0.0, 3.0)));
}

TEST(ConvexCorridorSampling, EverySampleIsInsideAndHasFixedZ)
{
  BiasSampler sampler(123456U);
  sampler.setConvexCorridor({square("A", 0.0, 0.0, 1.0, 1.0),
                             square("B", 3.0, 0.0, 5.0, 2.0)});
  sampler.setCorridorZ(7.25);

  for (int i = 0; i < 10000; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    EXPECT_TRUE(sampler.isInsideCorridor(Eigen::Vector2d(sample.x(), sample.y())));
    EXPECT_DOUBLE_EQ(7.25, sample.z());
  }
}

TEST(ConvexCorridorSampling, CorridorTakesPrecedenceOverInformedMode)
{
  BiasSampler sampler(99U);
  sampler.setConvexCorridor({square("A", 10.0, 10.0, 11.0, 11.0)});
  sampler.setCorridorZ(2.0);
  sampler.setInformedTransRot(Eigen::Vector3d::Zero(), Eigen::Matrix3d::Identity());
  sampler.setInformedSacling(Eigen::Vector3d::Ones());

  Eigen::Vector3d sample;
  sampler.samplingOnce(sample);
  EXPECT_TRUE(sampler.isInsideCorridor(Eigen::Vector2d(sample.x(), sample.y())));
  EXPECT_DOUBLE_EQ(2.0, sample.z());
}

TEST(ConvexCorridorSampling, RegionsAreWeightedByArea)
{
  BiasSampler sampler(4242U);
  sampler.setConvexCorridor({square("small", 0.0, 0.0, 1.0, 1.0),
                             square("large", 3.0, 0.0, 5.0, 2.0)});
  int large_samples = 0;
  const int sample_count = 20000;
  for (int i = 0; i < sample_count; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    if (sample.x() >= 3.0)
      ++large_samples;
  }
  const double large_fraction = static_cast<double>(large_samples) / sample_count;
  EXPECT_GT(large_fraction, 0.76);
  EXPECT_LT(large_fraction, 0.84);
}

TEST(ConvexCorridorValidation, StartAndGoalMustMatchSequenceEnds)
{
  BiasSampler sampler(1U);
  sampler.setConvexCorridor({square("first", 0.0, 0.0, 1.0, 1.0),
                             square("last", 2.0, 0.0, 3.0, 1.0)});
  std::string error;

  EXPECT_FALSE(sampler.validateCorridorEndpoints(
      Eigen::Vector3d(1.5, 0.5, 0.0), Eigen::Vector3d(2.5, 0.5, 0.0), &error));
  EXPECT_NE(std::string::npos, error.find("start"));

  EXPECT_FALSE(sampler.validateCorridorEndpoints(
      Eigen::Vector3d(0.5, 0.5, 0.0), Eigen::Vector3d(1.5, 0.5, 0.0), &error));
  EXPECT_NE(std::string::npos, error.find("goal"));

  EXPECT_TRUE(sampler.validateCorridorEndpoints(
      Eigen::Vector3d(0.0, 0.5, 0.0), Eigen::Vector3d(3.0, 0.5, 0.0), &error));
}

TEST(ConvexCorridorValidation, InvalidCorridorIsRejected)
{
  BiasSampler sampler(1U);
  path_plan::ConvexRegion2D concave;
  concave.id = "concave";
  concave.polygon = {Eigen::Vector2d(0.0, 0.0), Eigen::Vector2d(2.0, 0.0),
                     Eigen::Vector2d(1.0, 0.5), Eigen::Vector2d(2.0, 2.0),
                     Eigen::Vector2d(0.0, 2.0)};
  EXPECT_THROW(sampler.setConvexCorridor({concave}), std::invalid_argument);
}

TEST(RegionPriorSampling, SamplesStayInsideProvidedRegionsWithFixedZ)
{
  BiasSampler sampler(2026U);
  sampler.setRegionPrior({scoredSquare("low", 0.2, 0.0, 0.0, 1.0, 1.0),
                          scoredSquare("high", 0.8, 3.0, 0.0, 4.0, 1.0)});
  sampler.setRegionPriorZ(4.5);
  for (int i = 0; i < 10000; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    EXPECT_TRUE(sampler.isInsideRegionPrior(Eigen::Vector2d(sample.x(), sample.y())));
    EXPECT_DOUBLE_EQ(4.5, sample.z());
  }
}

TEST(RegionPriorSampling, RegionChoiceIsProportionalToScoresNotArea)
{
  BiasSampler sampler(8080U);
  sampler.setRegionPrior({scoredSquare("low", 0.2, 0.0, 0.0, 1.0, 1.0),
                          scoredSquare("high", 0.8, 3.0, 0.0, 5.0, 2.0)});
  int high_samples = 0;
  const int sample_count = 20000;
  for (int i = 0; i < sample_count; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    if (sample.x() >= 3.0)
      ++high_samples;
  }
  const double high_fraction = static_cast<double>(high_samples) / sample_count;
  EXPECT_GT(high_fraction, 0.76);
  EXPECT_LT(high_fraction, 0.84);
}

TEST(DensityDecay, UpdatesAtSuccessfulNodeIntervalAndKeepsBaseScores)
{
  BiasSampler sampler(123U);
  sampler.setRegionPrior({scoredSquare("A", 0.8, 0, 0, 1, 1),
                          scoredSquare("B", 0.8, 2, 0, 3, 1)});
  BiasSampler::DensityDecayConfig config;
  config.enabled = true;
  config.update_interval = 3;
  sampler.setDensityDecayConfig(config);
  std::vector<BiasSampler::DensityDecayRecord> records;
  sampler.setDensityDecayLogger([&](const BiasSampler::DensityDecayRecord &r) { records.push_back(r); });
  sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
  const Eigen::Vector3d a(0.5, 0.5, 0);
  sampler.recordAddedNode(a, 10);
  sampler.recordAddedNode(Eigen::Vector3d(4, 4, 0), 11); // outside every prior region
  EXPECT_TRUE(records.empty());
  EXPECT_DOUBLE_EQ(0.8, sampler.regionAdjustedScore("A"));
  sampler.recordAddedNode(a, 12);
  ASSERT_EQ(2U, records.size());
  EXPECT_EQ(3U, sampler.densityNodesAdded());
  EXPECT_EQ(2U, sampler.regionNodeCount("A"));
  EXPECT_EQ(0U, sampler.regionNodeCount("B"));
  EXPECT_EQ(12U, records[0].iteration);
  EXPECT_DOUBLE_EQ(0.8, sampler.regionBaseScore("A"));
  EXPECT_NEAR(0.6, sampler.regionAdjustedScore("A"), 1e-12);
  EXPECT_DOUBLE_EQ(0.8, sampler.regionAdjustedScore("B"));
  EXPECT_LT(records[0].probability_after, records[0].probability_before);
  const auto probabilities = sampler.regionProbabilities();
  EXPECT_NEAR(1.0, std::accumulate(probabilities.begin(), probabilities.end(), 0.0), 1e-12);
  for (double probability : probabilities) { EXPECT_TRUE(std::isfinite(probability)); EXPECT_GT(probability, 0.0); }
}

TEST(DensityDecay, ScoreIsMonotoneAndProtectedGoalDecaysLess)
{
  BiasSampler sampler(5U);
  sampler.setRegionPrior({scoredSquare("A", 0.8, 0, 0, 1, 1),
                          scoredSquare("B", 0.8, 2, 0, 3, 1)});
  BiasSampler::DensityDecayConfig config;
  config.enabled = true;
  config.update_interval = 2;
  sampler.setDensityDecayConfig(config);
  sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
  const Eigen::Vector3d a(0.5, 0.5, 0), b(2.5, 0.5, 0);
  sampler.recordAddedNode(a, 1); sampler.recordAddedNode(b, 2);
  EXPECT_NEAR(0.8 - 0.4 / 3.0, sampler.regionAdjustedScore("A"), 1e-12);
  EXPECT_NEAR(0.8 - 0.1 / 3.0, sampler.regionAdjustedScore("B"), 1e-12);
  const double previous = sampler.regionAdjustedScore("A");
  sampler.recordAddedNode(a, 3); sampler.recordAddedNode(b, 4);
  EXPECT_LE(sampler.regionAdjustedScore("A"), previous);
  EXPECT_GT(sampler.regionAdjustedScore("B"), sampler.regionAdjustedScore("A"));
  EXPECT_DOUBLE_EQ(0.8, sampler.regionBaseScore("B"));
}

TEST(DensityDecay, ResetAndBoundaryTieBreak)
{
  BiasSampler sampler(8U);
  sampler.setRegionPrior({scoredSquare("Z", 0.5, 0, 0, 1, 1),
                          scoredSquare("A", 0.5, 1, 0, 2, 1)});
  BiasSampler::DensityDecayConfig config;
  config.enabled = true; config.update_interval = 1;
  sampler.setDensityDecayConfig(config);
  sampler.beginDensityDecayRun(Eigen::Vector3d(1.5, 0.5, 0));
  sampler.recordAddedNode(Eigen::Vector3d(1, 0.5, 0), 1);
  EXPECT_EQ(1U, sampler.regionNodeCount("A"));
  EXPECT_EQ(0U, sampler.regionNodeCount("Z"));
  sampler.beginDensityDecayRun(Eigen::Vector3d(1.5, 0.5, 0));
  EXPECT_EQ(0U, sampler.regionNodeCount("A"));
  EXPECT_EQ(0U, sampler.densityNodesAdded());
  EXPECT_DOUBLE_EQ(0.5, sampler.regionAdjustedScore("A"));
  EXPECT_NEAR(0.5, sampler.regionProbabilities()[0], 1e-12);
}

TEST(DensityDecay, DisabledAndSequenceModesRetainStaticDistribution)
{
  const auto regions = std::vector<path_plan::ScoredConvexRegion2D>{
      scoredSquare("A", 0.2, 0, 0, 1, 1), scoredSquare("B", 0.8, 2, 0, 3, 1)};
  BiasSampler sampler(42U);
  sampler.setRegionPrior(regions);
  sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
  for (int i = 0; i < 20; ++i) sampler.recordAddedNode(Eigen::Vector3d(0.5, 0.5, 0), i);
  EXPECT_EQ(0U, sampler.densityNodesAdded());
  EXPECT_NEAR(0.2, sampler.regionProbabilities()[0], 1e-12);
  BiasSampler::DensityDecayConfig config; config.enabled = true; config.update_interval = 1;
  sampler.setDensityDecayConfig(config);
  path_plan::SequenceSamplingStrategy strategy;
  strategy.sequence = {"A", "B"}; strategy.regions = regions;
  sampler.setSequenceGuidance(strategy);
  sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
  sampler.recordAddedNode(Eigen::Vector3d(0.5, 0.5, 0), 1);
  EXPECT_EQ(0U, sampler.densityNodesAdded());
  EXPECT_NEAR(0.2, sampler.regionProbabilities()[0], 1e-12);
}

TEST(DensityDecay, FixedSeedReproducesSamplesAcrossEpochs)
{
  auto make_sampler = []() {
    BiasSampler sampler(2026U);
    sampler.setRegionPrior({scoredSquare("A", 0.7, 0, 0, 1, 1),
                            scoredSquare("B", 0.3, 2, 0, 3, 1)});
    BiasSampler::DensityDecayConfig config; config.enabled = true; config.update_interval = 2;
    sampler.setDensityDecayConfig(config);
    sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
    return sampler;
  };
  auto first = make_sampler(), second = make_sampler();
  for (int i = 0; i < 30; ++i)
  {
    Eigen::Vector3d one, two;
    first.samplingOnce(one); second.samplingOnce(two);
    EXPECT_TRUE(one.isApprox(two, 0.0));
    first.recordAddedNode(one, i); second.recordAddedNode(two, i);
  }
  EXPECT_EQ(first.regionProbabilities(), second.regionProbabilities());
}

TEST(DensityDecay, RejectsInvalidConfigurationAndZeroArea)
{
  BiasSampler sampler;
  BiasSampler::DensityDecayConfig config; config.update_interval = 0;
  EXPECT_THROW(sampler.setDensityDecayConfig(config), std::invalid_argument);
  auto invalid = scoredSquare("flat", 0.5, 0, 0, 1, 0);
  EXPECT_THROW(sampler.setRegionPrior({invalid}), std::invalid_argument);
}

TEST(DensityDecay, ZeroDensityUsesBaseOrConfiguredFloor)
{
  BiasSampler sampler(17U);
  sampler.setRegionPrior({scoredSquare("empty", 0.01, 0, 0, 1, 1),
                          scoredSquare("busy", 0.8, 2, 0, 3, 1)});
  BiasSampler::DensityDecayConfig config;
  config.enabled = true; config.update_interval = 1; config.min_score = 0.05;
  sampler.setDensityDecayConfig(config);
  sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
  EXPECT_DOUBLE_EQ(0.01, sampler.regionAdjustedScore("empty")); // no epoch yet
  sampler.recordAddedNode(Eigen::Vector3d(2.5, 0.5, 0), 1);
  EXPECT_DOUBLE_EQ(0.05, sampler.regionAdjustedScore("empty"));
  EXPECT_EQ(0U, sampler.regionNodeCount("empty"));
}

TEST(DensityDecay, InterleavedTreeInsertionsShareOneEpoch)
{
  BiasSampler sampler(31U);
  sampler.setRegionPrior({scoredSquare("A", 0.8, 0, 0, 1, 1),
                          scoredSquare("B", 0.8, 2, 0, 3, 1)});
  BiasSampler::DensityDecayConfig config; config.enabled = true; config.update_interval = 3;
  config.protected_region_ids.insert("A");
  sampler.setDensityDecayConfig(config);
  sampler.beginDensityDecayRun(Eigen::Vector3d(2.5, 0.5, 0));
  int updates = 0;
  sampler.setDensityDecayLogger([&](const BiasSampler::DensityDecayRecord &) { ++updates; });
  sampler.recordAddedNode(Eigen::Vector3d(0.5, 0.5, 0), 1); // tree A
  sampler.recordAddedNode(Eigen::Vector3d(2.5, 0.5, 0), 1); // tree B connect
  EXPECT_EQ(0, updates);
  sampler.recordAddedNode(Eigen::Vector3d(2.5, 0.5, 0), 1); // another connect node
  EXPECT_EQ(2, updates); // one record per region at the shared epoch
  EXPECT_EQ(3U, sampler.densityNodesAdded());
  EXPECT_EQ(1U, sampler.regionNodeCount("A"));
  EXPECT_EQ(2U, sampler.regionNodeCount("B"));
  // Same density would give the protected region a smaller subtraction.
  EXPECT_NEAR(0.8 - 0.1 / 3.0, sampler.regionAdjustedScore("A"), 1e-12);
}

TEST(RegionPriorValidation, EndpointsMayBeInAnyProvidedRegion)
{
  BiasSampler sampler(3U);
  sampler.setRegionPrior({scoredSquare("A", 0.9, 0.0, 0.0, 1.0, 1.0),
                          scoredSquare("B", 0.1, 2.0, 0.0, 3.0, 1.0)});
  std::string error;
  EXPECT_TRUE(sampler.validateGuidanceEndpoints(
      Eigen::Vector3d(2.5, 0.5, 0.0), Eigen::Vector3d(0.5, 0.5, 0.0), &error));
  EXPECT_FALSE(sampler.validateGuidanceEndpoints(
      Eigen::Vector3d(4.0, 0.5, 0.0), Eigen::Vector3d(0.5, 0.5, 0.0), &error));
  EXPECT_NE(std::string::npos, error.find("start"));
}

TEST(GuidanceModes, CorridorAndRegionPriorDoNotMix)
{
  BiasSampler sampler(7U);
  sampler.setConvexCorridor({square("corridor", 0.0, 0.0, 1.0, 1.0)});
  EXPECT_TRUE(sampler.corridorSamplingEnabled());
  EXPECT_FALSE(sampler.regionPriorSamplingEnabled());

  sampler.setRegionPrior({scoredSquare("prior", 1.0, 3.0, 0.0, 4.0, 1.0)});
  EXPECT_FALSE(sampler.corridorSamplingEnabled());
  EXPECT_TRUE(sampler.regionPriorSamplingEnabled());
}

TEST(GuidanceModes, DefaultNoneModeRetainsUniformMapSampling)
{
  BiasSampler sampler(11U);
  sampler.setSamplingRange(Eigen::Vector3d(-2.0, -3.0, -4.0),
                           Eigen::Vector3d(4.0, 6.0, 8.0));
  EXPECT_FALSE(sampler.corridorSamplingEnabled());
  EXPECT_FALSE(sampler.regionPriorSamplingEnabled());
  for (int i = 0; i < 1000; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    EXPECT_GE(sample.x(), -2.0);
    EXPECT_LE(sample.x(), 2.0);
    EXPECT_GE(sample.y(), -3.0);
    EXPECT_LE(sample.y(), 3.0);
    EXPECT_GE(sample.z(), -4.0);
    EXPECT_LE(sample.z(), 4.0);
  }
}

TEST(SequenceGuidedSampling, PreservesBiasAndGlobalExploration)
{
  BiasSampler sampler(20260930U);
  sampler.setSamplingRange(Eigen::Vector3d(0.0, 0.0, 0.0), Eigen::Vector3d(10.0, 1.0, 1.0));
  sampler.setPlanar(true);
  sampler.setGuidanceZ(0.0);
  path_plan::SequenceSamplingStrategy strategy;
  strategy.start_region = "low";
  strategy.goal_region = "high";
  strategy.sequence = {"low", "high"};
  strategy.regions = {scoredSquare("low", 0.1, 0.0, 0.0, 1.0, 1.0),
                      scoredSquare("high", 0.9, 2.0, 0.0, 3.0, 1.0)};
  strategy.guided_probability = 0.8;
  strategy.portal_probability = 0.0;
  sampler.setSequenceGuidance(strategy);

  int low = 0, high = 0, outside = 0;
  for (int i = 0; i < 30000; ++i)
  {
    Eigen::Vector3d sample; sampler.samplingOnce(sample);
    if (sample.x() <= 1.0) ++low;
    else if (sample.x() >= 2.0 && sample.x() <= 3.0) ++high;
    else ++outside;
  }
  EXPECT_TRUE(sampler.sequenceGuidedSamplingEnabled());
  EXPECT_GT(high, low * 4);       // sequence score changes the guided distribution
  EXPECT_GT(outside, 3000);       // configurable global exploration remains active
  EXPECT_LT(outside, 8000);
}

TEST(SequenceGuidedSampling, InvalidSequenceIsRejected)
{
  BiasSampler sampler(1U);
  path_plan::SequenceSamplingStrategy strategy;
  strategy.guided_probability = 0.8;
  EXPECT_THROW(sampler.setSequenceGuidance(strategy), std::invalid_argument);
}

TEST(PlanarBaseline, SamplesUseStartAltitude) {
  BiasSampler sampler(42);
  sampler.setSamplingRange(Eigen::Vector3d(0,0,-.5),Eigen::Vector3d(16,10,2));
  sampler.setPlanar(true);sampler.setGuidanceZ(.15);
  for(int i=0;i<100;++i) {
    Eigen::Vector3d p;sampler.samplingOnce(p);
    EXPECT_DOUBLE_EQ(p.z(),.15); EXPECT_GE(p.x(),0); EXPECT_LT(p.x(),16);
  }
}

TEST(InformedRegionPrior, SamplesRespectPriorAndRotatedEllipse) {
  BiasSampler sampler(42U);
  sampler.setRegionPrior({scoredSquare("region", 1, -3, -3, 3, 3)});
  sampler.setRegionPriorZ(0);
  sampler.setClipGuidanceToInformed(true);
  const Eigen::Matrix3d rotation = Eigen::AngleAxisd(0.7, Eigen::Vector3d::UnitZ()).toRotationMatrix();
  const Eigen::Vector3d center(.2,.3,0), radii(2,.5,1);
  sampler.setInformedTransRot(center, rotation);
  sampler.setInformedSacling(radii);
  for(int i=0;i<1000;++i) {
    Eigen::Vector3d p; sampler.samplingOnce(p);
    ASSERT_TRUE(p.allFinite());
    EXPECT_TRUE(sampler.isInsideRegionPrior(p.head<2>()));
    EXPECT_LE((rotation.transpose()*(p-center)).cwiseQuotient(radii).squaredNorm(),1+1e-12);
  }
}

TEST(InformedRegionPrior, DisjointDomainRejectsAndResetAllowsPriorAgain) {
  BiasSampler sampler(9U);
  sampler.setRegionPrior({scoredSquare("region", 1, 5, 5, 6, 6)});
  sampler.setRegionPriorZ(0);
  sampler.setClipGuidanceToInformed(true);
  sampler.setInformedTransRot(Eigen::Vector3d::Zero(),Eigen::Matrix3d::Identity());
  sampler.setInformedSacling(Eigen::Vector3d::Ones());
  Eigen::Vector3d p; sampler.samplingOnce(p);
  EXPECT_FALSE(p.allFinite());
  sampler.reset(); sampler.samplingOnce(p);
  EXPECT_TRUE(p.allFinite());
  EXPECT_TRUE(sampler.isInsideRegionPrior(p.head<2>()));
}

TEST(InformedRegionPrior, OrdinaryPriorIsNotClippedByDefault) {
  BiasSampler sampler(9U);
  sampler.setRegionPrior({scoredSquare("region", 1, 5, 5, 6, 6)});
  sampler.setInformedTransRot(Eigen::Vector3d::Zero(),Eigen::Matrix3d::Identity());
  sampler.setInformedSacling(Eigen::Vector3d::Ones());
  Eigen::Vector3d p; sampler.samplingOnce(p);
  EXPECT_TRUE(p.allFinite());
  EXPECT_GT(p.x(),5);
}
