import { lazy, Suspense } from "react";
import App from "./App";
import { useRoute } from "./router";

// The landing page is its own chunk, so the kiosk never downloads it.
const Landing = lazy(() => import("./landing/Landing"));

export default function Root() {
  const route = useRoute();
  if (route === "agent") return <App />;
  return (
    <Suspense fallback={null}>
      <Landing />
    </Suspense>
  );
}
