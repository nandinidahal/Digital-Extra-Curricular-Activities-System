import HeroSection from "../../components/home/HeroSection";
import ActivitiesSection from "../../components/home/ActivitiesSection";
import CategoriesSection from "../../components/home/CategoriesSection";
import HowItWorksSection from "../../components/home/HowItWorksSection";
import BenefitsSection from "../../components/home/BenefitsSection";
import AnnouncementsSection from "../../components/home/AnnouncementsSection";
import CallToActionSection from "../../components/home/CallToActionSection";

// The home page is a stack of sections. Reorder or remove them here.
export default function HomePage() {
  return (
    <>
      <HeroSection />
      <ActivitiesSection />
      <CategoriesSection />
      <HowItWorksSection />
      <BenefitsSection />
      <AnnouncementsSection />
      <CallToActionSection />
    </>
  );
}
