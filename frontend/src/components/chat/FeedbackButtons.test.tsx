import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FeedbackButtons } from "./FeedbackButtons";

describe("FeedbackButtons", () => {
  it("renders both rating buttons when no feedback has been given", () => {
    render(<FeedbackButtons feedback={undefined} onRate={vi.fn()} />);

    expect(screen.getByRole("button", { name: /was helpful/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /was not helpful/i })).toBeInTheDocument();
  });

  it("calls onRate with 'helpful' when the thumbs-up button is clicked", async () => {
    const onRate = vi.fn();
    const user = userEvent.setup();
    render(<FeedbackButtons feedback={undefined} onRate={onRate} />);

    await user.click(screen.getByRole("button", { name: /was helpful/i }));

    expect(onRate).toHaveBeenCalledWith("helpful");
  });

  it("calls onRate with 'not_helpful' when the thumbs-down button is clicked", async () => {
    const onRate = vi.fn();
    const user = userEvent.setup();
    render(<FeedbackButtons feedback={undefined} onRate={onRate} />);

    await user.click(screen.getByRole("button", { name: /was not helpful/i }));

    expect(onRate).toHaveBeenCalledWith("not_helpful");
  });

  it("shows a positive thank-you message and no buttons once rated helpful", () => {
    render(<FeedbackButtons feedback="helpful" onRate={vi.fn()} />);

    expect(screen.getByText(/thanks for the feedback/i)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows a different message once rated not helpful", () => {
    render(<FeedbackButtons feedback="not_helpful" onRate={vi.fn()} />);

    expect(screen.getByText(/we'll work on this/i)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
