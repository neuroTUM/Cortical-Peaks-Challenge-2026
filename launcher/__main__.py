from launcher import _parse_args, main_server, main_spectator

args = _parse_args()

if args.target == "server":
    main_server()
else:
    main_spectator()
