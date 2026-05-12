import { Outlet } from "react-router-dom";
import { MarketingHeader } from "../../components/marketing/MarketingHeader";
import { SectionNav } from "./components/SectionNav";

export function UsingAtlasLayout() {
  return (
    <div className="min-h-screen bg-[#f5f6f8]">
      <MarketingHeader activeNav="about" />
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="flex gap-10">
          {/* Sidebar */}
          <aside className="hidden pt-1 lg:block">
            <div className="sticky top-10">
              <SectionNav />
            </div>
          </aside>

          {/* Main content */}
          <main className="min-w-0 flex-1">
            <div className="max-w-[760px]">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
