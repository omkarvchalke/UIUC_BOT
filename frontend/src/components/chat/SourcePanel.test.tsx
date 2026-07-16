import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Citation } from "@/types/chat";

import { SourcePanel } from "./SourcePanel";

function baseCitation(overrides: Partial<Citation> = {}): Citation {
  return {
    title: "Parking Permits",
    url: "https://example.edu/parking",
    department: "Parking Department",
    topic: "transportation",
    subtopic: "Permits",
    fused_score: 0.842,
    rerank_score: null,
    ...overrides,
  };
}

async function openPanel(): Promise<void> {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /1 source/i }));
}

describe("SourcePanel", () => {
  it("renders nothing when there are no citations", () => {
    const { container } = render(<SourcePanel citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("hides subtopic and scores when debugMode is off", async () => {
    render(<SourcePanel citations={[baseCitation()]} />);
    await openPanel();

    expect(screen.getByText("Parking Permits")).toBeInTheDocument();
    expect(screen.queryByText("Permits")).not.toBeInTheDocument();
    expect(screen.queryByText(/fused:/)).not.toBeInTheDocument();
  });

  it("shows subtopic and fused score when debugMode is on", async () => {
    render(<SourcePanel citations={[baseCitation()]} debugMode />);
    await openPanel();

    expect(screen.getByText("Permits")).toBeInTheDocument();
    expect(screen.getByText("fused: 0.842")).toBeInTheDocument();
  });

  it("renders no rerank line when rerank_score is null, while fused_score still shows", async () => {
    render(<SourcePanel citations={[baseCitation({ rerank_score: null })]} debugMode />);
    await openPanel();

    expect(screen.getByText("fused: 0.842")).toBeInTheDocument();
    expect(screen.queryByText(/rerank:/)).not.toBeInTheDocument();
  });

  it("shows the rerank score when present", async () => {
    render(<SourcePanel citations={[baseCitation({ rerank_score: 0.913 })]} debugMode />);
    await openPanel();

    expect(screen.getByText("rerank: 0.913")).toBeInTheDocument();
  });
});
