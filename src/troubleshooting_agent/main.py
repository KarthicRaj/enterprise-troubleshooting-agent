from troubleshooting_agent.agent.graph import agent


def main() -> None:
    question = input("Describe the application issue: ").strip()

    if not question:
        print("Please enter an issue description.")
        return

    result = agent.invoke({"question": question})
    print("\n" + result["response"])


if __name__ == "__main__":
    main()
