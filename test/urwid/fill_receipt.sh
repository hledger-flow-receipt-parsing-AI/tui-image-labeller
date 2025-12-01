#!/bin/bash
# Start tmux session
tmux new-session -d -s urwid_session "python -m test.urwid.fill_receipt.py"

# Wait briefly to ensure TUI is ready
sleep 8

# Send commands to the tmux session
# Year
tmux send-keys -t urwid_session "202409101240" Enter
# tmux send-keys -t urwid_session "0" Enter
# tmux send-keys -t urwid_session "2" Enter
# tmux send-keys -t urwid_session "4" Enter

# # Month
# tmux send-keys -t urwid_session "0" Enter
# tmux send-keys -t urwid_session "9" Enter

sleep 2
# Day
tmux send-keys -t urwid_session "groceries:ekoplaza" Enter
sleep 1
# Bank payment
tmux send-keys -t urwid_session "12" Enter
sleep 1
tmux send-keys -t urwid_session "9" Enter
sleep 1
tmux send-keys -t urwid_session "17.34" Enter
sleep 1
tmux send-keys -t urwid_session "00" Enter
sleep 1

# Add another payment
tmux send-keys -t urwid_session "y" Enter
sleep 2
# Cash payment
tmux send-keys -t urwid_session "7" Enter # cash
sleep 1
tmux send-keys -t urwid_session "9" Enter # Eur
sleep 1
tmux send-keys -t urwid_session "8.90" Enter
sleep 1
tmux send-keys -t urwid_session "0" Enter
sleep 1
# tmux attach-session -t urwid_session
sleep 2

# A
tmux send-keys -t urwid_session "Right" Enter
sleep 2
tmux send-keys -t urwid_session "ekoplaza" Enter
tmux send-keys -t urwid_session "Groenestraat" Enter
tmux send-keys -t urwid_session "6531HE" Enter
tmux send-keys -t urwid_session "199" Enter

tmux send-keys -t urwid_session "Nijmegen" Enter

tmux send-keys -t urwid_session "Netherlands" Enter
tmux send-keys -t urwid_session "" Enter

tmux send-keys -t urwid_session "2.17" Enter
# tmux send-keys -t urwid_session "" Enter # Sumbit done with receipt.

# Attach to the session to make it visible
tmux attach-session -t urwid_session
