# Dike - Betting Bot Configuration

## Overview
This repository contains a configuration file (`setting.txt`) for a betting bot strategy. The logic is written in a custom pseudo-code format with comments in Indonesian (Bahasa Indonesia).

## Project Structure
- `setting.txt` — Core betting strategy configuration defining base bet, delay, loss/win streak management rules, and safety stops.

## Strategy Summary
- **Base Bet**: 100 IDR
- **Delay**: 300 ms
- **Loss Management**: Increases bet amount and adjusts win chance after 3–6 consecutive losses
- **Win Management**: Decreases or resets bet amount after win streaks
- **Safety Stop**: Stops the bot for 2 minutes if losses exceed 5000 IDR

## User Preferences
- No specific preferences recorded yet.
