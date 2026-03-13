import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("submits medication input and allows approve decision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          reconciled_medication: "Metformin 500mg twice daily",
          confidence_score: 0.88,
          reasoning: "Primary care note is the most recent high-reliability source.",
          recommended_actions: ["Update the hospital chart."],
          clinical_safety_check: "PASSED",
        }),
      }),
    );

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Run reconciliation" }));

    await waitFor(() => {
      expect(screen.getByText("Metformin 500mg twice daily")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByText(/Current review status:/)).toHaveTextContent("approved");
  });
});
